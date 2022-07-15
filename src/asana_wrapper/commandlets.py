import functools
from argparse import Namespace, ArgumentParser
from collections import defaultdict
from datetime import datetime, timedelta
from timeit import default_timer as timer

from AsanaProject import AsanaProject
from AsanaTask import AsanaTask, TaskNameParser
from AsanaSection import AsanaSection
from NameParser import NameParser

from constants import epics_section_name, stories_section_name, completion_sprint_name, sprints_section_name, \
    priority_name, \
    estimate_hours_name, completed_hours_name, remaining_hours_name, estimate_days_name, remaining_days_name, \
    hours_per_day, done_section_name

import plotly.graph_objects as go


def cmdlet(action: str, title: str):
    def decorator_cmdlet(cls):
        cls.action = action
        cls.title = title

        @functools.wraps(cls)
        def wrapper_cmdlet(*args, **kwargs):
            instance = cls(*args, **kwargs)
            return instance

        return wrapper_cmdlet

    return decorator_cmdlet


class Commandlet:
    action: str = None
    title: str = None

    def __init__(self, project: AsanaProject):
        self._project: AsanaProject = project

    def _execute(self, args: Namespace):
        pass

    def visit(self, parser: ArgumentParser):
        pass

    def run(self, args: Namespace):
        start = timer()
        if self.title is not None:
            print(f"## {self.title}")
        self._execute(args)
        if self.title is not None:
            end = timer()
            print(f"{self.title} took {end - start} seconds")


@cmdlet(action="add-stories", title="Add all the stories taken from the epics which are not yet completed")
class AddStories(Commandlet):
    def _execute(self, args):
        epics = self._project.get_section(epics_section_name)
        stories = self._project.get_section(stories_section_name)
        stories_tasks = set(stories.tasks())
        epics_tasks = set(subtask for task in epics.tasks() for subtask in task.subtasks() if not subtask.completed)
        missing = epics_tasks - stories_tasks
        for task_id in missing:
            print(f"* Adding missing story {task_id}")
            stories.attach_task(task_id)


@cmdlet(action="assign-sprint", title="Assigns all the tasks completed in a sprint to the corresponding sprint task")
class AssignTasksToSprint(Commandlet):
    def _execute(self, args):
        sprints = dict()
        print("### Retrieving sprints")
        for sprint in self._project.get_section(sprints_section_name).tasks():
            sprint_number = sprint.field_value(completion_sprint_name)
            if sprint_number is not None:
                sprints[sprint_number] = sprint

        for task in self._project.get_section(epics_section_name).tasks(recursive=True):
            if task.completed:
                sprint_number = task.field_value(completion_sprint_name)
                if sprint_number is not None:
                    sprint = sprints.get(sprint_number)
                    if sprint is not None:
                        print(f"* Assigning task {task} to sprint {sprint}")
                        sprint.attach_subtask(task)


@cmdlet(action="build-hierarchy", title="Build the task hierarchy based on the name of the tasks")
class BuildHierarchy(Commandlet):
    def _execute(self, args):
        for name in args.section_names:
            section = self._project.get_section(name)
            parent_section = self._project.get_section(args.parent) if args.parent is not None else section

            if section is None:
                print(f"### Section {name} not found")
                continue

            print(f"### Building hierarchy for {section.name} looking into {parent_section.name}")
            for task in section.tasks(recursive=args.recursive):
                print(f"* Checking task {task}")
                self.__build_hierarchy(task, parent_section)

    def visit(self, parser: ArgumentParser):
        parser.add_argument("section_names", nargs="+",
                            help="The name of the sections in which to build the task hierarchy")
        parser.add_argument("-r", "--recursive", action="store_true",
                            help="Scans the tasks recursively while building the hierarchy", default=False)
        parser.add_argument("-p", "--parent", help="The section in which to look for root tasks", default=None)

    def __build_hierarchy(self, task: AsanaTask, section: AsanaSection):
        parser = TaskNameParser(task)

        if len(parser.parts) == 1:
            return

        self._attach_parent(task, parser.first, section)
        task.name = parser.tagged_name
        self.__build_hierarchy(task, section)

    @staticmethod
    def _attach_parent(task: AsanaTask, name: str, section: AsanaSection):
        print(f"* Attaching parent {name} to {task}")
        if task.parent is None:
            print(f"* Task {task} has no parent")
            tasks = section.tasks()
        else:
            print(f"* Task {task} has parent {task.parent}")
            tasks = task.parent.subtasks()
        parent = next((found for found in tasks if (not found.completed) and NameParser(found.name).matches(name)),
                      None)
        print(f"* Parent {parent} found")
        if parent is None:
            if task.parent is None:
                print(f"* Parent {name} not found in {section}")
                parent = section.add_task(name)
            else:
                print(f"* Parent {name} not found in {task.parent}")
                parent = task.parent.add_subtask(name)
        task.parent = parent


@cmdlet(action="rename-tasks", title="Rename tasks according to hierarchy")
class RenameTasks(Commandlet):
    def _execute(self, args):
        for name in args.section_names:
            section = self._project.get_section(name)
            if section is None:
                print(f"### Section {name} not found")
                continue

            print(f"### Renaming tasks in {section.name}")
            for task in section.tasks(recursive=args.no_recursive):
                task.name = TaskNameParser(task).tagged_name
                print(task)

    def visit(self, parser: ArgumentParser):
        parser.add_argument("section_names", nargs="+", help="The name of the section for which to rename tasks")
        parser.add_argument("-n", "--no-recursive", action="store_false", help="Does not rename subtasks", default=True)


@cmdlet(action="sort-tasks", title="Sorts the tasks in the sections")
class SortTasks(Commandlet):
    def __init__(self, project: AsanaProject):
        super().__init__(project)

    def _execute(self, args):
        for name in args.section_names:
            section = self._project.get_section(name)
            if section is None:
                print(f"### Section {name} not found")
                continue

            print(f"### Sorting tasks in section {section.name}")
            tasks = list(section.tasks())
            tasks.sort(key=self._key_extractor(args.sort_by))
            previous_task = None
            for task in tasks:
                print(task)
                section.attach_task(task, previous_task)
                previous_task = task

    def visit(self, parser: ArgumentParser):
        parser.add_argument("section_names", nargs="+", help="The name of the section for which to rename tasks")
        parser.add_argument("-s", "--sort-by", dest="sort_by", default="name", help="The field to sort by",
                            choices=["name", "due", "start", "priority", "parent-start"])

    def _key_extractor(self, sort_by: str):
        if sort_by == "name":
            return lambda task: task.name
        elif sort_by == "due":
            return lambda task: task.due_on
        elif sort_by == "start":
            return lambda task: task.start_on
        elif sort_by == "parent-start":
            return lambda task: task.parent.start_on if task.parent is not None else task.start_on
        elif sort_by == "priority":
            return self._task_priority
        else:
            return lambda task: task.name

    @staticmethod
    def _task_priority(task: AsanaTask) -> str:
        priorities = defaultdict(lambda: 4, {"Must Have": 0, "Should Have": 1, "Could Have": 2, "Won't Have": 3})
        return f"{priorities[task.field_value(priority_name)]} {task.name}"


@cmdlet(action="split-task", title="Splits a task by putting all incomplete subtasks into a new one")
class SplitTask(Commandlet):
    def __init__(self, project: AsanaProject):
        super().__init__(project)

    # Returns a task ID given its url
    @staticmethod
    def _task_id(url: str) -> str:
        return url.split("/")[-2]

    # given a task id creates a new task assigning all incomplete subtasks to it
    def _execute(self, args):
        task_id = self._project.task_id(args.task_url)
        section = self._project.get_section(args.section_name)
        if section is None:
            print(f"### Section {args.section_name} not found")
            return

        task = next((task for task in section.tasks() if task.gid == task_id), None)
        if task is None:
            print(f"### Task {task_id} not found")
            return

        print(f"### Splitting task {task}")
        new_task = self._project.get_section(args.section_name).add_task("Split from " + task.name)

        for subtask in task.subtasks():
            if subtask.completed:
                print(f"* Skipping completed subtask {subtask}")
                continue
            print(f"* Moving subtask {subtask}")
            subtask.parent = new_task

        print(f"* Marking task {task} as completed")
        task.completed = True

    def visit(self, parser: ArgumentParser):
        parser.add_argument("-s", "--section", dest="section_name", default="Stories",
                            help="The name of the section in which there is the task to split")
        parser.add_argument("-t", "--task", dest="task_url", help="The url of the task to split")


@cmdlet(action="spread-task", title="Spreads a task by attaching its subtasks into a given section")
class SpreadTask(Commandlet):
    def __init__(self, project: AsanaProject):
        super().__init__(project)

    def _execute(self, args):
        task_id = self._project.task_id(args.task_url)
        source_section = self._project.get_section(args.source_section)
        destination_section = self._project.get_section(args.destination_section)
        if source_section is None:
            print(f"### Section {args.source_section} not found")
            return

        if destination_section is None:
            print(f"### Section {args.destination_section} not found")
            return

        task = next((task for task in source_section.tasks() if task.gid == task_id), None)
        if task is None:
            print(f"### Task {task_id} not found")
            return

        print(f"### Spreading task {task} in {destination_section}")
        for subtask in task.subtasks():
            print(f"* Attaching subtask {subtask}")
            destination_section.attach_task(subtask)

    def visit(self, parser: ArgumentParser):
        parser.add_argument("-s", "--source", dest="source_section", default="Stories",
                            help="The name of the section in which there is the task to spread")
        parser.add_argument("-d", "--destination", dest="destination_section", default="To Do",
                            help="The name of the section in which to put the subtasks")
        parser.add_argument("-t", "--task", dest="task_url", help="The url of the task whose subtasks will be spread")


@cmdlet(action="update-estimates", title="Update the estimates for a given task or all the tasks in a section")
class UpdateEstimatesForTask(Commandlet):
    def __init__(self, project: AsanaProject):
        super().__init__(project)

    def _execute(self, args):
        source_section = self._project.get_section(args.source_section)
        if source_section is None:
            print(f"### Section {args.source_section} not found")
            return

        if args.task_url is None:
            for task in source_section.tasks():
                task.reduce(self.__initialize_task, self.__increment_estimate, self.__update_estimate)
        else:
            task_id = self._project.task_id(args.task_url)
            task = next((task for task in source_section.tasks() if task.gid == task_id), None)
            if task is None:
                print(f"### Task {args.task_url} not found")
                return
            task.reduce(self.__initialize_task, self.__increment_estimate, self.__update_estimate)

    def visit(self, parser: ArgumentParser):
        parser.add_argument("-s", "--source", dest="source_section", default="Epics",
                            help="The name of the section in which there is the task to update")
        parser.add_argument("-t", "--task", dest="task_url", help="The url of the task whose subtasks will be spread",
                            default=None)

    @staticmethod
    def __update_estimate(task: AsanaTask, current):
        print(f"* Updating task {task}")
        current = current or (0, 0, 0)
        task.update_field(estimate_hours_name, current[0])
        task.update_field(completed_hours_name, current[1])
        task.update_field(remaining_hours_name, current[2])
        task.update_field(estimate_days_name, round(current[0] / hours_per_day, 1))
        task.update_field(remaining_days_name, round(current[2] / hours_per_day, 1))

    @staticmethod
    def __initialize_task(task: AsanaTask):
        print(f"* Initializing task {task}")
        estimate = task.field_value(estimate_hours_name) or 0
        completed = estimate if task.completed else 0
        remaining = estimate - completed
        task.update_field(remaining_hours_name, remaining)
        task.update_field(completed_hours_name, completed)
        task.update_field(estimate_days_name, round(estimate / hours_per_day, 1))
        task.update_field(remaining_days_name, round(remaining / hours_per_day, 1))

    @staticmethod
    def __increment_estimate(task: AsanaTask, current):
        current = current or (0, 0, 0)
        estimate = task.field_value(estimate_hours_name) or 0
        completed = task.field_value(completed_hours_name) or 0
        remaining = task.field_value(remaining_hours_name) or 0
        return current[0] + estimate, current[1] + completed, current[2] + remaining


@cmdlet(action="close-sprint", title="Close the current sprint")
class CloseSprint(Commandlet):
    def _execute(self, args: Namespace):
        print(f"### Closing sprint {args.sprint_number}")
        done_tasks = self._project.get_section(done_section_name).tasks()
        sprint = next((sprint for sprint in self._project.get_section(sprints_section_name).tasks()
                       if sprint.field_value(completion_sprint_name) == args.sprint_number), None)
        epics = dict((TaskNameParser(t).mnemonic, t) for t in self._project.get_section(epics_section_name).tasks())

        if sprint is None:
            print(f"### Sprint {args.sprint_number} not found")
            return

        task: AsanaTask
        for task in done_tasks:
            if not task.completed:
                continue
            if task.field_value(completion_sprint_name) is None:
                print(f"* Assigning task {task} to sprint {args.sprint_number}")
                task.update_field(completion_sprint_name, args.sprint_number)
                sprint.attach_subtask(task)
                self._project.remove_from_task(task)

                print(f"* Commenting task {task}")
                parts = [part.strip() for part in task.name.split(">")]
                if len(parts) == 1:
                    continue

                name = parts[0]
                if name not in epics:
                    print(f"* Could not find epic {name}")
                    continue

                epic = epics[name]
                epic.add_comment(f"{task.url} - Completed on {sprint.url}")

    def visit(self, parser: ArgumentParser):
        parser.add_argument("-s", "--sprint-number", type=int, dest="sprint_number", help="The sprint number to close",
                            required=True)


# Counts the story points for all the tasks in the project
@cmdlet(action="plot-burndown", title="Plots the burndown chart for a given sprint within the project")
class PlotBurndown(Commandlet):
    @staticmethod
    def shirt_value(value: str) -> int:
        if value == "🐁   - Small":
            return 1
        if value == "🐄   - Medium":
            return 3
        if value == "🐘   - Large":
            return 8
        return 0

    def _execute(self, args: Namespace):
        completed_events = dict()
        added_events = dict()
        start = self._project.start_on - timedelta(days=1)

        print(f"### Counting story points")
        story_points = 0
        added_points = 0
        for section in self._project.sections():
            for task in section.tasks():
                shirt_size = task.field_value("👕  Size")
                points = self.shirt_value(shirt_size)
                if task.date_added_to_project <= start + timedelta(days=1):
                    story_points += points

                print(f"* {task} = {points}")
                if task.completed:
                    if task.completed_at.date() not in completed_events:
                        completed_events[task.completed_at.date()] = 0
                    completed_events[task.completed_at.date()] += points

                if task.date_added_to_project > start + timedelta(days=1):
                    print(f"** Added {points} points on {task.date_added_to_project}")
                    if task.date_added_to_project not in completed_events:
                        completed_events[task.date_added_to_project] = 0
                    completed_events[task.date_added_to_project] -= points
                    if task.date_added_to_project not in added_events:
                        added_events[task.date_added_to_project] = 0
                    added_events[task.date_added_to_project] += points
                    added_points += points

        print(f"### Total story points: {story_points} + {added_points} added")
        result = []
        points = []
        burndown = story_points
        while start <= self._project.due_on:
            if start in completed_events:
                burndown -= completed_events[start]

            added = 0
            if start in added_events:
                added += added_events[start]

            if start <= datetime.today().date():
                result.append(burndown)
                points.append(added)
            start += timedelta(days=1)
        self.draw_burndown_chart(self._project.name, self._project.start_on, self._project.due_on,
                                 story_points, added_points, result, points)

    @staticmethod
    def draw_burndown_chart(sprint_name, start_date, end_date, story_points, added_points, progress, tasks_added):
        def compute_burndown_line(start_date, end_date, story_points):
            def compute_delta_days(start, end):
                delta_days = 0
                while start < end:
                    start += timedelta(days=1)
                    if start.weekday() < 5:
                        delta_days += 1
                return delta_days

            burndown_line = []
            date_line = []
            days = compute_delta_days(start_date, end_date)
            i = 0
            while start_date <= end_date:
                date_line.append(start_date)
                start_date += timedelta(days=1)
                burndown_line.append(story_points - (i * story_points / days))
                if start_date.weekday() < 5:
                    i += 1
            return date_line, burndown_line

        data = []
        x, y = compute_burndown_line(start_date, end_date, story_points)
        trace = go.Scatter(
            x=x,
            y=y,
            mode='lines+markers',
            name='Ideal'
        )
        actual = go.Scatter(
            x=x,
            y=progress,
            mode="lines+markers",
            name="Actual"
        )

        added = go.Bar(
            x=x,
            y=tasks_added,
            name="Added"
        )
        data.append(trace)
        data.append(actual)
        data.append(added)
        layout = go.Layout(
            title=f"Burndown Chart for Sprint {sprint_name} ({story_points} story points + {added_points} added)",
            xaxis=dict(
                title='Date',
                range=[start_date, end_date]
            ),
            yaxis=dict(
                title='Story Points',
                range=[0, story_points]
            )
        )
        fig = go.Figure(data=data, layout=layout)
        fig.show()
