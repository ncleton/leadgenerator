"""Public, versioned Lead Generator SDK surface for plugin authors."""

from leadgenerator.kernel.composition import LEADGENERATOR_SDK_VERSION
from leadgenerator.kernel.contracts import (
    ActionDescriptor,
    CampaignDefinition,
    Evidence,
    Observation,
    ProspectOutcome,
    ScoreContribution,
    ScorecardDefinition,
    UiConfiguration,
    UiPanelContribution,
    UiTabContribution,
    WorkspaceViewModel,
)
from leadgenerator.kernel.plugins import (
    PLUGIN_API_VERSION,
    PLUGIN_PROTOCOL_VERSION,
    PluginContext,
    PluginManifest,
    UiShellProvider,
    UiShellResource,
)

__all__ = [
    "LEADGENERATOR_SDK_VERSION",
    "PLUGIN_API_VERSION",
    "PLUGIN_PROTOCOL_VERSION",
    "ActionDescriptor",
    "CampaignDefinition",
    "Evidence",
    "Observation",
    "PluginContext",
    "PluginManifest",
    "ProspectOutcome",
    "ScoreContribution",
    "ScorecardDefinition",
    "UiConfiguration",
    "UiPanelContribution",
    "UiShellProvider",
    "UiShellResource",
    "UiTabContribution",
    "WorkspaceViewModel",
]
