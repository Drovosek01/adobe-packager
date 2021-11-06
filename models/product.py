from typing import Any, List


class Dependency:
    def __init__(self, id: str, version: str, buildGuid: str, app_json: dict = None):
        self.id = id
        self.version = version
        self.buildGuid = buildGuid
        self.app_json = app_json


class Product:
    def __init__(self, id: str, name: str, version: str, platform: str, dependencies: List[Dependency], buildGuid: str, language: str = 'en_US', app_json: dict[Any, Any] = None):
        self.id = id
        self.name = name
        self.version = version
        self.platform = platform
        self.dependencies = dependencies
        self.buildGuid = buildGuid
        self.language = language
        self.app_json = app_json
        self.install_name = f'Install {self.id}_{self.version}-{self.language}-{self.platform}.app'
