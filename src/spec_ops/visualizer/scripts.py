"""Client-side JavaScript aggregator for the SpecOps Visualizer."""

from .drawer_script import DRAWER_JS
from .gantt_script import GANTT_JS
from .graph_script import GRAPH_JS
from .layouts_script import LAYOUTS_JS
from .routing_script import ROUTING_JS
from .views_script import VIEWS_JS

VISUALIZER_JS = f"""
(function() {{
{GRAPH_JS}
{LAYOUTS_JS}
{DRAWER_JS}
{GANTT_JS}
{VIEWS_JS}
{ROUTING_JS}
}})();
"""
