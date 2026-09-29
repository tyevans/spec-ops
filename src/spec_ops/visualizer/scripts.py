"""Client-side JavaScript aggregator for the SpecOps Visualizer."""

from .drawer_script import DRAWER_JS
from .gantt_script import GANTT_JS
from .graph_script import GRAPH_JS
from .views_script import VIEWS_JS

VISUALIZER_JS = f"""
(function() {{
{GRAPH_JS}
{DRAWER_JS}
{GANTT_JS}
{VIEWS_JS}
}})();
"""
