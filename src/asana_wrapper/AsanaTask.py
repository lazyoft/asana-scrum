from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Generator, Callable, Any, List

import dateutil.parser

from NameParser import NameParser


class TaskNameParser(NameParser):
    def __init__(self, task: AsanaTask):
        super().__init__(task.name)
        self.task = task

    @property
    def path(self) -> str:
        path = self.mnemonic
        parent = self.task.parent
        while parent is not None:
            path = TaskNameParser(parent).mnemonic + " > " + path
            parent = parent.parent
        return path

    @property
    def tags(self):
        paths = []
        parent = self.task.parent
        while parent is not None:
            paths.append(TaskNameParser(parent).mnemonic)
            parent = parent.parent
        return " ".join(reversed(paths))

    @property
    def tagged_name(self) -> str:
        if self.tags:
            return f"[{self.tags}] {self.remainder or self.untagged}"
        else:
            return self.remainder or self.untagged


class AsanaTask:

    def __init__(self, task, asana_client, opt_fields):
        self.__date_added_to_project = None
        self._task = task
        self._client = asana_client
        self._opt_fields = opt_fields
        self.__parent = None
        self.__subtasks = None

    @property
    def gid(self) -> str:
        return self._task["gid"]

    @property
    def name(self) -> str:
        return self._task["name"]

    @property
    def url(self) -> str:
        return self._task["permalink_url"]

    @name.setter
    def name(self, value: str) -> None:
        if self._task["name"] != value:
            self._task["name"] = value
            self._client.tasks.update_task(self.gid, {"name": value})

    @property
    def parent(self) -> AsanaTask | None:
        if self._task["parent"] is None:
            return None
        if self.__parent is None:
            self.__parent = AsanaTask(self._client.tasks.get_task(self._task["parent"]["gid"], opt_fields=self._opt_fields), self._client,
                                      self._opt_fields)
        return self.__parent

    @parent.setter
    def parent(self, value: AsanaTask):
        print(f"Setting parent of {self} to {value}")
        self.__parent = value
        self._client.tasks.set_parent_for_task(self.gid, {"parent": value.gid})
        self._task = self._client.tasks.get_task(self.gid, opt_fields=self._opt_fields)

    @property
    def completed(self) -> bool:
        return self._task["completed"]

    @completed.setter
    def completed(self, value: bool):
        if value != self._task["completed"]:
            self._task["completed"] = value
            self._client.tasks.update_task(self.gid, self._task)

    @property
    def completed_at(self) -> datetime:
        return dateutil.parser.parse(self._task["completed_at"]) if self._task["completed_at"] else None

    @property
    def created_at(self) -> datetime:
        return dateutil.parser.parse(self._task["created_at"])

    @property
    def start_on(self) -> datetime:
        return dateutil.parser.parse(self._task["start_on"] or datetime.date.max.isoformat())

    @start_on.setter
    def start_on(self, value: datetime):
        if value != self._task["start_on"]:
            self._task["start_on"] = value
            self._client.tasks.update_task(self.gid, self._task)

    @property
    def due_on(self) -> datetime:
        if self._task["due_on"] is None:
            return None
        return dateutil.parser.parse(self._task["due_on"])

    @due_on.setter
    def due_on(self, value: datetime):
        if value != self._task["due_on"]:
            self._task["due_on"] = value
            self._client.tasks.update_task(self.gid, self._task)

    @property
    def notes(self) -> str:
        return self._task["notes"]

    @notes.setter
    def notes(self, value: str):
        if value != self._task["notes"]:
            self._task["notes"] = value
            self._client.tasks.update_task(self.gid, self._task)

    @property
    def stories(self) -> List[Any]:
        return list(self._client.stories.get_stories_for_task(self.gid))

    @property
    def date_added_to_project(self):
        if self.__date_added_to_project is not None:
            return self.__date_added_to_project
        
        stories = reversed(self.stories)
        for story in stories:
            if story["resource_subtype"] == "added_to_project" and story["type"] == "system":
                self.__date_added_to_project = dateutil.parser.parse(story["created_at"]).date()
                return self.__date_added_to_project
            
        self.__date_added_to_project = datetime.date.min
        return self.__date_added_to_project

    def subtasks(self, recursive: bool = False) -> Generator[AsanaTask]:
        if self.__subtasks is None:
            self.__subtasks = list((AsanaTask(task, self._client, self._opt_fields) for task in
                                    self._client.tasks.get_subtasks_for_task(self.gid, opt_fields=self._opt_fields)))
        yield from self.__subtasks
        if recursive:
            for task in self.__subtasks:
                yield from task.subtasks(recursive)

    def __leveled_subtasks(self, level: int = 0) -> Generator[AsanaTask]:
        tasks = ((level, task) for task in self.subtasks())
        for task in tasks:
            yield task
            yield from task[1].__leveled_subtasks(level + 1)

    def reduce(self, initializer: Callable[[AsanaTask], None], reducer: Callable[[AsanaTask, Any], Any], updater: Callable[[AsanaTask, Any], None]):
        levels = defaultdict(lambda: None)
        prev_level = -1
        for subtask in reversed(list(self.__leveled_subtasks())):
            initializer(subtask[1])
            if subtask[0] < prev_level:
                updater(subtask[1], levels[prev_level])
                levels[prev_level] = None
            levels[subtask[0]] = reducer(subtask[1], levels[subtask[0]])
            prev_level = subtask[0]
        initializer(self)
        updater(self, levels[0])

    def add_subtask(self, name: str) -> AsanaTask:
        task = AsanaTask(self._client.tasks.create_subtask_for_task(self.gid, {"name": name}), self._client, self._opt_fields)
        self.__subtasks.append(task)
        return task

    def attach_subtask(self, task: str or AsanaTask, after: str or AsanaTask = None) -> AsanaTask:
        gid = task.gid if isinstance(task, AsanaTask) else task
        insert_after = after.gid if isinstance(after, AsanaTask) else after
        task.name = TaskNameParser(task).path
        if insert_after is not None:
            self._client.tasks.set_parent_for_task(gid, {"parent": self.gid, "insert_after": insert_after})
        else:
            self._client.tasks.set_parent_for_task(gid, {"parent": self.gid})
        return task

    def _field(self, field_name: str) -> dict:
        return next((field for field in self._task["custom_fields"] if field["name"] == field_name), None)

    def field_value(self, field_name: str) -> Any:
        field = self._field(field_name)
        if field is None:
            return None
        result = field[field["type"] + "_value"] if field["type"] != "multi_enum" else field["display_value"]
        return result if result is None or type(result) in (int, float, bool, str) else result["name"]

    def update_field(self, field_name: str, value: Any):
        current_value = self.field_value(field_name)
        if current_value != value:
            field = self._field(field_name)
            if field is None:
                return
            update_field = field["type"] + "_value" if field["type"] != "multi_enum" else "display_value"
            field[update_field] = value
            self._client.tasks.update_task(self._task["gid"], {"custom_fields": {self._field(field_name)["gid"]: value}})

    def add_comment(self, comment: str):
        self._client.stories.create_story_for_task(self.gid, {"text": comment})

    def __str__(self):
        return f"({self.gid}) {self.name}"

    def __hash__(self):
        return hash(self.gid)

    def __eq__(self, other):
        if isinstance(other, AsanaTask):
            return self.gid == other.gid
        return False
