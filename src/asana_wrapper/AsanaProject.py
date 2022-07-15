from __future__ import annotations

import datetime
from typing import Generator

import asana
import dateutil.parser

from .AsanaSection import AsanaSection
from .AsanaTask import AsanaTask


class AsanaProject:
    def __init__(self, access_token: str, project_id: str):
        self._client = asana.Client.access_token(access_token)
        self._client.headers["Asana-Enable"] = "new_user_task_lists"
        self._client.headers["Asana-Disable"] = "new_project_templates"
        self._project_id = project_id
        self._opt_fields = "name, parent, custom_fields, completed, completed_at, created_at, start_on, due_on, notes, permalink_url"
        self.__project = self._client.projects.get_project(self._project_id)
        self.__name = self.__project["name"]
        self.__start_on = (dateutil.parser.parse(self.__project["start_on"] or datetime.date.min.isoformat())).date()
        self.__due_on = (dateutil.parser.parse(self.__project["due_on"] or datetime.date.min.isoformat())).date()

    @staticmethod
    def task_id(url: str) -> str:
        return url.split("/")[-2]

    @property
    def gid(self) -> str:
        return self._project_id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def start_on(self) -> datetime:
        return self.__start_on

    @property
    def due_on(self) -> datetime:
        return self.__due_on

    def get_section(self, section_name: str) -> AsanaSection or None:
        sections = self._client.sections.get_sections_for_project(self._project_id)
        for section in sections:
            if section['name'] == section_name:
                return AsanaSection(section, self._client, self._project_id, self._opt_fields)
        return None

    def remove_from_task(self, task: AsanaTask):
        self._client.tasks.remove_project_for_task(task.gid, {"project": self._project_id})

    def sections(self) -> Generator[AsanaSection]:
        sections = self._client.sections.get_sections_for_project(self._project_id)
        yield from (AsanaSection(section, self._client, self._project_id, self._opt_fields) for section in sections)