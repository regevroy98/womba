"""Unit tests for JiraClient."""

import asyncio
from unittest import mock
from unittest.mock import AsyncMock

import pytest

from src.aggregator.jira_client import JiraClient


class TestJiraClient:
    """Test suite for JiraClient."""

    def test_get_issue_success(self, sample_jira_issue_data):
        """Test successful issue retrieval."""
        mock_sdk = mock.Mock()
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            sdk_client=mock_sdk,
        )

        async def _exercise():
            with mock.patch.object(
                client,
                "_call_jira",
                AsyncMock(return_value=sample_jira_issue_data),
            ) as mock_call:
                story = await client.get_issue("PROJ-123")
                return story, mock_call

        story, mock_call = asyncio.run(_exercise())

        assert story.key == "PROJ-123"
        assert story.summary == "Add user authentication feature"
        assert story.issue_type == "Story"
        assert story.status == "In Progress"
        assert story.priority == "High"
        assert "authentication" in story.labels
        assert "Backend" in story.components
        mock_call.assert_awaited_once_with(
            mock_sdk.issue,
            "PROJ-123",
            expand='renderedFields,changelog',
        )

    def test_get_issue_not_found(self):
        """Test issue not found error."""
        mock_sdk = mock.Mock()
        client = JiraClient(sdk_client=mock_sdk)

        async def _exercise():
            with mock.patch.object(
                client,
                "_call_jira",
                AsyncMock(side_effect=Exception("Issue not found")),
            ):
                await client.get_issue("INVALID-999")

        with pytest.raises(Exception):
            asyncio.run(_exercise())

    def test_parse_issue_with_adf_description(
        self, sample_jira_issue_data
    ):
        """Test parsing issue with Atlassian Document Format description."""
        sample_jira_issue_data["fields"]["description"] = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "This is ADF formatted text"}],
                }
            ],
        }

        client = JiraClient(sdk_client=mock.Mock())
        story = client._parse_issue(sample_jira_issue_data)

        assert "This is ADF formatted text" in story.description

    def test_extract_acceptance_criteria_from_description(
        self,
    ):
        """Test extraction of acceptance criteria from description."""
        fields = {
            "summary": "Test feature",
            "issuetype": {"name": "Story"},
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "reporter": {"emailAddress": "test@example.com"},
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-01-01T00:00:00.000+0000",
        }
        description = """
        Feature description here.

        Acceptance Criteria
        - Criterion 1
        - Criterion 2

        Additional notes.
        """

        client = JiraClient(sdk_client=mock.Mock())
        ac = client._extract_acceptance_criteria(fields, description)

        assert ac is not None
        assert "Criterion 1" in ac or "criterion 1" in ac.lower()

    def test_search_issues(self, sample_jira_issue_data):
        """Test searching issues with JQL."""
        mock_sdk = mock.Mock()
        client = JiraClient(sdk_client=mock_sdk)

        async def _exercise():
            with mock.patch.object(
                client,
                "_call_jira",
                AsyncMock(return_value={"issues": [sample_jira_issue_data], "total": 1}),
            ) as mock_call:
                stories = await client.search_issues("project = PROJ", max_results=10)
                return stories, mock_call

        stories, mock_call = asyncio.run(_exercise())

        assert len(stories) == 1
        assert stories[0].key == "PROJ-123"
        mock_call.assert_awaited_once_with(
            mock_sdk.jql,
            "project = PROJ",
            limit=10,
            start=0,
            fields=[
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
            ],
            expand='renderedFields',
        )

    def test_get_linked_issues(
        self, sample_jira_issue_data
    ):
        """Test fetching linked issues."""
        linked_issue_data = sample_jira_issue_data.copy()
        linked_issue_data["key"] = "PROJ-124"

        main_issue_with_links = sample_jira_issue_data.copy()
        main_issue_with_links["fields"]["issuelinks"] = [
            {"inwardIssue": {"key": "PROJ-124"}}
        ]

        mock_sdk = mock.Mock()
        client = JiraClient(sdk_client=mock_sdk)

        async def _exercise():
            with mock.patch.object(
                client,
                "_get_issue_raw",
                AsyncMock(return_value=main_issue_with_links),
            ) as mock_get_raw, mock.patch.object(
                client,
                "get_issue",
                AsyncMock(return_value=client._parse_issue(linked_issue_data)),
            ) as mock_get_issue:
                linked_stories = await client.get_linked_issues("PROJ-123")
                return linked_stories, mock_get_raw, mock_get_issue

        linked_stories, mock_get_raw, mock_get_issue = asyncio.run(_exercise())

        assert len(linked_stories) == 1
        assert linked_stories[0].key == "PROJ-124"
        mock_get_raw.assert_awaited_once_with("PROJ-123")
        mock_get_issue.assert_awaited_once_with("PROJ-124")
