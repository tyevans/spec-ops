from .cluster_script import CLUSTER_JS
from .drawer_script import DRAWER_JS
from .filter_script import FILTER_JS
from .gantt_script import GANTT_JS
from .graph_script import GRAPH_JS
from .layouts_script import LAYOUTS_JS
from .lead_console import LEAD_CONSOLE_JS
from .matrix import MATRIX_JS
from .routing_script import ROUTING_JS
from .views_script import VIEWS_JS

VISUALIZER_JS = f"""
(function() {{
{GRAPH_JS}
{CLUSTER_JS}
{FILTER_JS}
{LAYOUTS_JS}
{DRAWER_JS}
{GANTT_JS}
{VIEWS_JS}
{MATRIX_JS}
{LEAD_CONSOLE_JS}
{ROUTING_JS}
}})();
"""
