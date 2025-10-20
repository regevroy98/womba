"""Configuration manager for the Womba CLI.

This module needs to operate even in very minimal environments where optional
dependencies like ``httpx`` or ``loguru`` might not be installed.  The
implementation therefore falls back to the standard library when those
packages are unavailable and simply disables cloud synchronisation features
that require them.
"""

from pathlib import Path
from typing import Optional

import json

try:  # pragma: no cover - optional dependency in CLI usage
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback to json for tests
    yaml = None

try:  # pragma: no cover - exercised in environments without optional deps
    import httpx
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    httpx = None  # type: ignore[assignment]

try:  # pragma: no cover - exercised when loguru is missing
    from loguru import logger
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal envs
    import logging

    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())

from src.config.user_config import WombaConfig


class ConfigManager:
    """Manages Womba configuration with local + cloud sync"""
    
    def __init__(self):
        self.config_dir = Path.home() / ".womba"
        self.config_file = self.config_dir / "config.yml"
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Optional[WombaConfig]:
        """Load config from local file, then try cloud sync"""
        local_config = self._load_local()
        
        if (
            local_config
            and local_config.womba_api_key
            and httpx is not None
        ):
            # Try to sync with cloud
            try:
                cloud_config = self._load_cloud(local_config.womba_api_key)
                if cloud_config:
                    # Merge: local overrides cloud
                    merged = self._merge_configs(cloud_config, local_config)
                    return merged
            except Exception as e:
                logger.warning(f"Could not sync with cloud: {e}")
        
        return local_config
    
    def save(self, config: WombaConfig, sync_cloud: bool = True) -> None:
        """Save config to local file and optionally sync to cloud"""
        # Save locally
        self._save_local(config)
        
        # Sync to cloud if enabled
        if sync_cloud and config.womba_api_key and httpx is not None:
            try:
                self._save_cloud(config)
            except Exception as e:
                logger.warning(f"Could not sync to cloud: {e}")
    
    def exists(self) -> bool:
        """Check if config file exists"""
        return self.config_file.exists()
    
    def _load_local(self) -> Optional[WombaConfig]:
        """Load config from local YAML file"""
        if not self.config_file.exists():
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                if yaml is not None:
                    data = yaml.safe_load(f) or {}
                else:  # pragma: no cover - exercised when yaml missing
                    data = json.load(f)
            return WombaConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading local config: {e}")
            return None

    def _save_local(self, config: WombaConfig) -> None:
        """Save config to local YAML file"""
        try:
            with open(self.config_file, 'w') as f:
                if yaml is not None:
                    yaml.safe_dump(config.to_dict(), f, default_flow_style=False)
                else:  # pragma: no cover - exercised when yaml missing
                    json.dump(config.to_dict(), f, indent=2)
            logger.info(f"Config saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving local config: {e}")
            raise
    
    def _load_cloud(self, api_key: str) -> Optional[WombaConfig]:
        """Load config from Womba cloud API"""
        if httpx is None:  # pragma: no cover - exercised without httpx
            logger.debug("Cloud sync disabled because httpx is unavailable")
            return None

        try:
            response = httpx.get(
                "https://womba.onrender.com/api/v1/config/sync",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return WombaConfig.from_dict(data)
            elif response.status_code == 404:
                # No cloud config yet
                return None
            else:
                logger.warning(f"Cloud sync failed: {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Cloud sync error: {e}")
            return None
    
    def _save_cloud(self, config: WombaConfig) -> None:
        """Save config to Womba cloud API"""
        if httpx is None:  # pragma: no cover - exercised without httpx
            logger.debug("Skipping cloud config save because httpx is missing")
            return None

        try:
            response = httpx.post(
                "https://womba.onrender.com/api/v1/config/sync",
                headers={"Authorization": f"Bearer {config.womba_api_key}"},
                json=config.to_dict(),
                timeout=10.0
            )
            
            if response.status_code in (200, 201):
                logger.info("Config synced to cloud")
            else:
                logger.warning(f"Cloud sync failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"Cloud sync error: {e}")
    
    def _merge_configs(self, cloud: WombaConfig, local: WombaConfig) -> WombaConfig:
        """Merge configs with local taking precedence"""
        merged = WombaConfig()
        
        # For each field, use local if set, otherwise cloud
        for field_name in cloud.to_dict().keys():
            local_val = getattr(local, field_name)
            cloud_val = getattr(cloud, field_name)
            
            # Use local value if it's not the default/empty
            if local_val and local_val != WombaConfig().to_dict().get(field_name):
                setattr(merged, field_name, local_val)
            else:
                setattr(merged, field_name, cloud_val)
        
        return merged
    
    def detect_git_provider(self, repo_path: str) -> str:
        """Detect git provider from remote URL"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "-C", repo_path, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                remote_url = result.stdout.strip().lower()
                if "github.com" in remote_url:
                    return "github"
                elif "gitlab.com" in remote_url or "gitlab" in remote_url:
                    return "gitlab"
        except Exception as e:
            logger.warning(f"Could not detect git provider: {e}")
        
        return "auto"
    
    def get_git_remote_url(self, repo_path: str) -> Optional[str]:
        """Get git remote URL"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "-C", repo_path, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Could not get git remote URL: {e}")
        
        return None

