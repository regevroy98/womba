"""Jira client for fetching stories and issues using the Atlassian SDK."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:  # pragma: no cover - allow running without Atlassian SDK installed
    from atlassian import Jira
except ModuleNotFoundError:  # pragma: no cover - tests may inject a stub client
    Jira = Any  # type: ignore[assignment]
try:  # pragma: no cover - allow running without loguru installed
    from loguru import logger
except ModuleNotFoundError:  # pragma: no cover - fallback to stdlib logging
    import logging

    logger = logging.getLogger(__name__)

from src.aggregator.atlassian_base import AtlassianClientBase, AtlassianCredentials

try:  # pragma: no cover - allow running without pydantic models installed
    from src.models.story import JiraStory
except ModuleNotFoundError:  # pragma: no cover - fallback dataclass for tests
    @dataclass
    class JiraStory:  # type: ignore[override]
        key: str
        summary: str
        description: str
        issue_type: str
        status: str
        priority: str
        assignee: Optional[str]
        reporter: str
        created: Optional[datetime]
        updated: Optional[datetime]
        labels: List[str]
        components: List[str]
        acceptance_criteria: Optional[str]
        linked_issues: List[str]
        attachments: List[str]
        custom_fields: Dict[str, Any]


class JiraClient(AtlassianClientBase):
    """Client for interacting with Jira API via the Atlassian SDK."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        credentials: Optional[AtlassianCredentials] = None,
        sdk_client: Optional[Jira] = None,
    ) -> None:
        """Initialize Jira client with shared Atlassian credentials."""

        super().__init__(
            credentials=credentials,
            base_url=base_url,
            email=email,
            api_token=api_token,
        )

        self.jira = sdk_client or Jira(
            url=self.base_url,
            username=self.email,
            password=self.api_token,
            cloud=True,
        )

        logger.info(f"Initialized Jira client for {self.base_url}")

    async def _call_jira(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute a Jira SDK call in a worker thread."""

        return await asyncio.to_thread(func, *args, **kwargs)

    def _extract_text_from_adf(self, adf_content: Any) -> str:
        """
        Extract plain text and URLs from Atlassian Document Format (ADF) JSON.
        Handles text nodes, link marks, and inlineCard nodes (for Confluence links).
        
        Args:
            adf_content: ADF content (dict or str)
            
        Returns:
            Plain text extracted from ADF with URLs included
        """
        logger.debug(f"Extracting text from ADF (type: {type(adf_content).__name__})")
        
        if isinstance(adf_content, str):
            return adf_content
        
        if not isinstance(adf_content, dict):
            return str(adf_content) if adf_content else ""
        
        text_parts = []
        
        def extract_recursive(node):
            if isinstance(node, dict):
                node_type = node.get('type')
                
                # Extract text node
                if node_type == 'text':
                    text = node.get('text', '')
                    if text:
                        text_parts.append(text)
                    
                    # If this text node has link marks, also add the URL
                    if 'marks' in node:
                        for mark in node.get('marks', []):
                            if mark.get('type') == 'link':
                                href = mark.get('attrs', {}).get('href', '')
                                if href:
                                    # Add the URL right after the link text
                                    text_parts.append(f' [{href}] ')
                
                # Extract inlineCard nodes (Confluence/Jira links) - CRITICAL FOR CONFLUENCE!
                elif node_type == 'inlineCard':
                    url = node.get('attrs', {}).get('url', '')
                    if url:
                        logger.info(f"Found inlineCard URL: {url}")
                        text_parts.append(f' {url} ')
                
                # Add newlines for paragraphs
                if node_type == 'paragraph':
                    text_parts.append('\n')
                
                # Recurse into content
                if 'content' in node:
                    for child in node['content']:
                        extract_recursive(child)
                        
            elif isinstance(node, list):
                for item in node:
                    extract_recursive(item)
        
        extract_recursive(adf_content)
        return ' '.join(text_parts)
    
    async def get_issue_comments(self, issue_key: str) -> List[Dict]:
        """
        Fetch all comments for a Jira issue.
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            
        Returns:
            List of comment objects with author, body, and created timestamp
        """
        logger.info(f"Fetching comments for: {issue_key}")

        data = await self._call_jira(self.jira.issue_get_comments, issue_key)

        comments = []
        for comment in data.get('comments', []):
            author = comment.get('author', {}).get('displayName', 'Unknown')
            body = comment.get('body', '')
            created = comment.get('created', '')

            if isinstance(body, dict):
                body = self._extract_text_from_adf(body)

            comments.append(
                {
                    'author': author,
                    'body': body,
                    'created': created,
                }
            )

        logger.info(f"Found {len(comments)} comments for {issue_key}")
        return comments

    async def get_issue_with_subtasks(self, issue_key: str) -> tuple[JiraStory, List[JiraStory]]:
        """
        Fetch issue and its subtasks using Jira SDK (more reliable than REST API).
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            Tuple of (main_story, subtasks)
        """
        try:
            issue = await self._call_jira(
                self.jira.issue,
                issue_key,
                expand='subtasks,renderedFields,changelog',
            )

            main_story = self._parse_issue(issue)

            subtasks = []
            for subtask in issue.get('fields', {}).get('subtasks', []):
                subtask_key = subtask.get('key')
                if not subtask_key:
                    continue
                try:
                    subtask_story = await self.get_issue(subtask_key)
                    subtasks.append(subtask_story)
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning(f"Could not fetch subtask {subtask_key}: {exc}")

            logger.info(f"Found {len(subtasks)} subtasks for {issue_key}")
            return main_story, subtasks

        except Exception as exc:
            logger.error(f"Error fetching subtasks with SDK: {exc}")
            main_story = await self.get_issue(issue_key)
            return main_story, []

    async def get_issue(self, issue_key: str) -> JiraStory:
        """
        Fetch a single Jira issue by key.

        Args:
            issue_key: Jira issue key (e.g., PROJ-123)

        Returns:
            JiraStory object

        Raises:
            Exception: If the Jira SDK request fails
        """
        logger.info(f"Fetching Jira issue: {issue_key}")

        data = await self._call_jira(
            self.jira.issue,
            issue_key,
            expand='renderedFields,changelog',
        )

        return self._parse_issue(data)

    async def get_linked_issues(self, issue_key: str) -> List[JiraStory]:
        """
        Fetch all issues linked to the given issue.

        Args:
            issue_key: Jira issue key

        Returns:
            List of linked JiraStory objects
        """
        logger.info(f"Fetching linked issues for: {issue_key}")

        # First get the main issue to get link information
        main_issue_data = await self._get_issue_raw(issue_key)
        links = main_issue_data.get("fields", {}).get("issuelinks", [])

        linked_stories = []
        for link in links:
            # Links can be inward or outward
            linked_issue_data = link.get("inwardIssue") or link.get("outwardIssue")
            if linked_issue_data:
                linked_key = linked_issue_data["key"]
                try:
                    story = await self.get_issue(linked_key)
                    linked_stories.append(story)
                except Exception as e:
                    logger.warning(f"Failed to fetch linked issue {linked_key}: {e}")

        return linked_stories

    async def search_issues(
        self, jql: str, max_results: int = 50, start_at: int = 0
    ) -> List[JiraStory]:
        """
        Search for issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return
            start_at: Starting index for pagination

        Returns:
            List of JiraStory objects
        """
        logger.info(f"Searching Jira issues with JQL: {jql}")

        fields = [
            "summary",
            "description",
            "issuetype",
            "status",
            "priority",
            "assignee",
            "reporter",
            "created",
            "updated",
            "labels",
            "components",
            "attachment",
            "issuelinks",
        ]

        data = await self._call_jira(
            self.jira.jql,
            jql,
            limit=max_results,
            start=start_at,
            fields=fields,
            expand='renderedFields',
        )

        issues = data.get("issues", [])
        return [self._parse_issue(issue) for issue in issues]

    async def _get_issue_raw(self, issue_key: str) -> Dict[str, Any]:
        """Get raw issue data from Jira API."""
        return await self._call_jira(
            self.jira.issue,
            issue_key,
            expand='renderedFields',
        )

    def _parse_issue(self, issue_data: Dict[str, Any]) -> JiraStory:
        """
        Parse raw Jira issue data into JiraStory model.

        Args:
            issue_data: Raw issue data from Jira API

        Returns:
            JiraStory object
        """
        fields = issue_data.get("fields", {})

        # Extract basic fields
        key = issue_data.get("key", "")
        summary = fields.get("summary", "")
        # Extract description (handle ADF format)
        description_raw = fields.get("description")
        description = self._extract_text_from_adf(description_raw)

        # Handle new Atlassian Document Format (ADF) for description
        if isinstance(description, dict):
            description = self._extract_text_from_adf(description)

        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        status = fields.get("status", {}).get("name", "Unknown")
        priority = fields.get("priority", {}).get("name", "Medium")

        # Extract people
        assignee_data = fields.get("assignee")
        assignee = assignee_data.get("emailAddress") if assignee_data else None

        reporter_data = fields.get("reporter", {})
        reporter = reporter_data.get("emailAddress", "unknown@example.com")

        # Extract dates
        created = self._parse_datetime(fields.get("created"))
        updated = self._parse_datetime(fields.get("updated"))

        # Extract arrays
        labels = fields.get("labels", [])
        components = [c.get("name", "") for c in fields.get("components", [])]

        # Extract attachments
        attachments = [
            att.get("content", "") for att in fields.get("attachment", [])
        ]

        # Extract linked issues
        issuelinks = fields.get("issuelinks", [])
        linked_issues = []
        for link in issuelinks:
            linked_issue = link.get("inwardIssue") or link.get("outwardIssue")
            if linked_issue:
                linked_issues.append(linked_issue.get("key", ""))

        # Extract custom fields
        custom_fields = {}
        for field_key, field_value in fields.items():
            if field_key.startswith("customfield_") and field_value is not None:
                custom_fields[field_key] = field_value

        # Try to find acceptance criteria in common custom field names or description
        acceptance_criteria = self._extract_acceptance_criteria(fields, description)

        return JiraStory(
            key=key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            status=status,
            priority=priority,
            assignee=assignee,
            reporter=reporter,
            created=created,
            updated=updated,
            labels=labels,
            components=components,
            acceptance_criteria=acceptance_criteria,
            linked_issues=linked_issues,
            attachments=attachments,
            custom_fields=custom_fields,
        )


    def _parse_datetime(self, date_str: Optional[str]) -> datetime:
        """Parse Jira datetime string."""
        if not date_str:
            return datetime.utcnow()
        try:
            # Jira uses ISO 8601 format
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.utcnow()

    def _extract_acceptance_criteria(
        self, fields: Dict[str, Any], description: str
    ) -> Optional[str]:
        """
        Try to extract acceptance criteria from various sources.

        Args:
            fields: Issue fields
            description: Issue description

        Returns:
            Acceptance criteria string or None
        """
        # Check common custom field names for acceptance criteria
        ac_field_names = [
            "customfield_10100",  # Common AC field
            "customfield_10200",
            "Acceptance Criteria",
        ]

        for field_name in ac_field_names:
            ac_value = fields.get(field_name)
            if ac_value:
                if isinstance(ac_value, str):
                    return ac_value
                elif isinstance(ac_value, dict):
                    return self._extract_text_from_adf(ac_value)

        # Try to find AC in description
        if description and "acceptance criteria" in description.lower():
            parts = description.lower().split("acceptance criteria")
            if len(parts) > 1:
                # Get the part after "acceptance criteria"
                ac_part = parts[1].split("\n\n")[0]  # Until next paragraph
                return ac_part.strip()

        return None

