"""
Unit tests for tool profiles configuration.
"""

import pytest
from configs.tool_profiles import (
    ToolProfile,
    NONE_PROFILE,
    SEARCH_ONLY_PROFILE,
    CODE_INTEL_PROFILE,
    DEEP_SEARCH_PROFILE,
    PROFILES,
    get_profile,
    list_profiles,
    get_profile_info,
    get_mcp_profiles,
)


class TestToolProfile:
    """Test ToolProfile dataclass"""
    
    def test_profile_creation(self):
        """Can create a ToolProfile"""
        profile = ToolProfile(
            name="test",
            description="Test profile",
            tools=["file_read", "bash_execute"],
            environment_vars={"TOKEN": "abc123"},
            mcp_enabled=False,
        )
        assert profile.name == "test"
        assert len(profile.tools) == 2
        assert not profile.mcp_enabled
    
    def test_profile_to_dict(self):
        """Profile converts to dict correctly"""
        profile = ToolProfile(
            name="test",
            description="Test profile",
            tools=["file_read"],
            environment_vars={"TOKEN": "abc"},
            mcp_enabled=True,
        )
        d = profile.to_dict()
        assert d["name"] == "test"
        assert d["mcp_enabled"] is True
        assert "tools" in d
        assert "environment_vars" in d


class TestPredefinedProfiles:
    """Test predefined profile constants"""
    
    def test_none_profile(self):
        """NONE_PROFILE is baseline without MCP"""
        assert NONE_PROFILE.name == "none"
        assert not NONE_PROFILE.mcp_enabled
        assert "file_read" in NONE_PROFILE.tools
        assert "bash_execute" in NONE_PROFILE.tools
        assert "sourcegraph_deep_search" not in NONE_PROFILE.tools
    
    def test_search_only_profile(self):
        """SEARCH_ONLY_PROFILE has basic search"""
        assert SEARCH_ONLY_PROFILE.name == "search_only"
        assert not SEARCH_ONLY_PROFILE.mcp_enabled
        assert "basic_search" in SEARCH_ONLY_PROFILE.tools
        assert "sourcegraph_deep_search" not in SEARCH_ONLY_PROFILE.tools
    
    def test_code_intel_profile(self):
        """CODE_INTEL_PROFILE has code intelligence tools"""
        assert CODE_INTEL_PROFILE.name == "code_intel"
        assert CODE_INTEL_PROFILE.mcp_enabled
        assert "symbol_search" in CODE_INTEL_PROFILE.tools
        assert "code_navigation" in CODE_INTEL_PROFILE.tools
        assert "semantic_search" in CODE_INTEL_PROFILE.tools
        assert "sourcegraph_deep_search" not in CODE_INTEL_PROFILE.tools
    
    def test_deep_search_profile(self):
        """DEEP_SEARCH_PROFILE has full Deep Search integration"""
        assert DEEP_SEARCH_PROFILE.name == "deep_search"
        assert DEEP_SEARCH_PROFILE.mcp_enabled
        assert "sourcegraph_deep_search" in DEEP_SEARCH_PROFILE.tools
        assert "sourcegraph_context" in DEEP_SEARCH_PROFILE.tools
        assert "sourcegraph_insights" in DEEP_SEARCH_PROFILE.tools
    
    def test_all_profiles_registered(self):
        """All predefined profiles in PROFILES registry"""
        assert "none" in PROFILES
        assert "search_only" in PROFILES
        assert "code_intel" in PROFILES
        assert "deep_search" in PROFILES
        assert len(PROFILES) == 4


class TestProfileRegistry:
    """Test profile registry functions"""
    
    def test_get_profile_none(self):
        """Can retrieve none profile"""
        profile = get_profile("none")
        assert profile.name == "none"
        assert profile is PROFILES["none"]
    
    def test_get_profile_search_only(self):
        """Can retrieve search_only profile"""
        profile = get_profile("search_only")
        assert profile.name == "search_only"
    
    def test_get_profile_code_intel(self):
        """Can retrieve code_intel profile"""
        profile = get_profile("code_intel")
        assert profile.name == "code_intel"
    
    def test_get_profile_deep_search(self):
        """Can retrieve deep_search profile"""
        profile = get_profile("deep_search")
        assert profile.name == "deep_search"
    
    def test_get_profile_unknown(self):
        """Unknown profile raises ValueError"""
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile("unknown")
    
    def test_list_profiles(self):
        """list_profiles returns all profile names"""
        profiles = list_profiles()
        assert len(profiles) == 4
        assert "none" in profiles
        assert "search_only" in profiles
        assert "code_intel" in profiles
        assert "deep_search" in profiles
        # Check they're sorted
        assert profiles == sorted(profiles)


class TestProfileInfo:
    """Test profile information functions"""
    
    def test_get_profile_info_none(self):
        """get_profile_info returns correct data for none profile"""
        info = get_profile_info("none")
        assert info["name"] == "none"
        assert info["mcp_enabled"] is False
        assert info["tool_count"] == len(NONE_PROFILE.tools)
        assert isinstance(info["tools"], list)
    
    def test_get_profile_info_deep_search(self):
        """get_profile_info includes deep_search tools"""
        info = get_profile_info("deep_search")
        assert info["name"] == "deep_search"
        assert info["mcp_enabled"] is True
        assert "sourcegraph_deep_search" in info["tools"]
        assert info["tool_count"] == 12
    
    def test_get_profile_info_unknown(self):
        """get_profile_info raises for unknown profile"""
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile_info("unknown")


class TestMCPProfiles:
    """Test MCP profile filtering"""
    
    def test_get_mcp_profiles(self):
        """get_mcp_profiles returns only MCP-enabled profiles"""
        mcp = get_mcp_profiles()
        assert len(mcp) == 2
        assert "code_intel" in mcp
        assert "deep_search" in mcp
        assert "none" not in mcp
        assert "search_only" not in mcp
    
    def test_none_profile_not_mcp(self):
        """NONE_PROFILE explicitly disables MCP"""
        assert not NONE_PROFILE.mcp_enabled
    
    def test_search_only_not_mcp(self):
        """SEARCH_ONLY_PROFILE does not have MCP"""
        assert not SEARCH_ONLY_PROFILE.mcp_enabled


class TestToolHierarchy:
    """Test that profiles have correct tool hierarchy"""
    
    def test_tools_progressive(self):
        """Tools increase with profile sophistication"""
        none_tools = set(NONE_PROFILE.tools)
        search_tools = set(SEARCH_ONLY_PROFILE.tools)
        intel_tools = set(CODE_INTEL_PROFILE.tools)
        deep_tools = set(DEEP_SEARCH_PROFILE.tools)
        
        # Each profile should include previous tools
        assert none_tools.issubset(search_tools)  # search_only has all of none
        assert search_tools.issubset(intel_tools)  # code_intel has all of search_only
        assert intel_tools.issubset(deep_tools)   # deep_search has all of code_intel
    
    def test_profile_toolset_sizes(self):
        """Profiles have increasing tool counts"""
        assert len(NONE_PROFILE.tools) == 5
        assert len(SEARCH_ONLY_PROFILE.tools) == 6
        assert len(CODE_INTEL_PROFILE.tools) == 9
        assert len(DEEP_SEARCH_PROFILE.tools) == 12


class TestEnvironmentVariables:
    """Test environment variable configuration"""
    
    def test_none_profile_no_env(self):
        """NONE_PROFILE has empty Sourcegraph credentials"""
        assert NONE_PROFILE.environment_vars["SRC_ACCESS_TOKEN"] == ""
        assert NONE_PROFILE.environment_vars["SOURCEGRAPH_URL"] == ""
    
    def test_search_only_has_env(self):
        """SEARCH_ONLY_PROFILE references environment variables"""
        assert "${SRC_ACCESS_TOKEN}" in SEARCH_ONLY_PROFILE.environment_vars["SRC_ACCESS_TOKEN"]
    
    def test_deep_search_mcp_config(self):
        """DEEP_SEARCH_PROFILE includes MCP_CONFIG env var"""
        assert "MCP_CONFIG" in DEEP_SEARCH_PROFILE.environment_vars
        assert "${MCP_CONFIG}" in DEEP_SEARCH_PROFILE.environment_vars["MCP_CONFIG"]
    
    def test_all_profiles_have_src_token(self):
        """All profiles define SRC_ACCESS_TOKEN"""
        for profile in PROFILES.values():
            assert "SRC_ACCESS_TOKEN" in profile.environment_vars


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
