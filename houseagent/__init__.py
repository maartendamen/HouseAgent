import sys
import os

db_name = 'houseagent.db'
db_location = os.path.join(sys.prefix, 'share', 'HouseAgent', db_name)

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

template_plugin_dir = os.path.join(template_dir, 'plugins')
