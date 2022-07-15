from __future__ import annotations

from typing import Generator

from AsanaTask import AsanaTask


class AsanaSection:
    def __init__(self, section, asana_client, project_id, opt_fields):
        self._section = section
        self._client = asana_client
        self._opt_fields = opt_fields
        self._project_id = project_id

    @property
    def name(self) -> str:
        return self._section["name"]

    @property
    def gid(self) -> str:
        return self._section["gid"]

    def tasks(self, recursive: bool = False) -> Generator[AsanaTask]:
        tasks = list((AsanaTask(task, self._client, self._opt_fields) for task in
                      self._client.tasks.get_tasks_for_section(self.gid, opt_fields=self._opt_fields)))
        yield from tasks
        if recursive:
            for task in tasks:
                yield from task.subtasks(recursive)

    def add_task(self, name: str) -> AsanaTask:
        return self.attach_task(AsanaTask(self._client.tasks.create_task({"name": name, "projects": self._project_id}), self._client,
                                          self._opt_fields))

    def attach_task(self, task: AsanaTask or str, after: str or AsanaTask = None) -> AsanaTask:
        gid = task.gid if isinstance(task, AsanaTask) else task
        insert_after = after.gid if isinstance(after, AsanaTask) else after
        if insert_after is not None:
            self._client.sections.add_task_for_section(self.gid, {"task": gid, "insert_after": insert_after})
        else:
            self._client.sections.add_task_for_section(self.gid, {"task": gid})
        return task

    def __str__(self):
        return f"({self.gid}) {self.name}"
