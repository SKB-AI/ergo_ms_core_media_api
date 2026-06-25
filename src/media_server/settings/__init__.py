from media_server.deploy import get_settings_module

_settings_module = get_settings_module()

if _settings_module.endswith('.production'):
    from media_server.settings.production import *  # noqa: F403
else:
    from media_server.settings.development import *  # noqa: F403
