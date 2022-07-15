from __future__ import annotations

from argparse import ArgumentParser

from asana_wrapper.AsanaProject import AsanaProject
from asana_wrapper.commandlets import Commandlet
import configparser


def read_properties():
    config = configparser.RawConfigParser()
    config.read('asana.properties')
    token = config.get('default', 'token')
    project_id = config.get('default', 'project_id')
    return token, project_id


def main():
    token, project_id = read_properties()
    parser = ArgumentParser(description="Performs scrum related activities on an Asana board")
    subparsers = parser.add_subparsers()
    project = AsanaProject(token, project_id)

    cmdlets = [cls(project) for cls in Commandlet.__subclasses__() if cls.action is not None]
    for cmd in cmdlets:
        subparser = subparsers.add_parser(cmd.action, help=cmd.title)
        subparser.set_defaults(cmdlet=cmd)
        cmd.visit(subparser)

    args = parser.parse_args()
    if "cmdlet" in args:
        args.cmdlet.run(args=args)
    else:
        parser.print_help()
    exit(0)


if __name__ == "__main__":
    main()


