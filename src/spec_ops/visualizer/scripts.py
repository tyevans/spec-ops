"""Client-side JavaScript aggregator for the SpecOps Visualizer."""

from .drawer_script import DRAWER_JS
from .graph_script import GRAPH_JS

VISUALIZER_JS = f"""
(function() {{
{GRAPH_JS}
{DRAWER_JS}
}})();
"""
