import argparse

from universal_scheduler import (
    UNIVERSAL_SCHEDULER_PATH,
    UniversalSchedulerValidationError,
    compile_universal_scheduler,
    validate_universal_scheduler,
    write_universal_scheduler,
    write_universal_scheduler_template,
)


def print_issue_report(error):
    print("Universal scheduler needs attention:")
    print()
    for issue in error.issues:
        print(f"- {issue}")
    print()
    print("Fix the lines above, then run the command again.")


def main():
    parser = argparse.ArgumentParser(
        description="Validate, compile, or export the single-file scheduler source."
    )
    parser.add_argument(
        "--export-current",
        action="store_true",
        help="Write the current repo files into UNIVERSAL_SCHEDULER.md.",
    )
    parser.add_argument(
        "--write-template",
        action="store_true",
        help="Write a generic ministry starter file to UNIVERSAL_SCHEDULER.template.md.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate UNIVERSAL_SCHEDULER.md without writing generated files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Compile from UNIVERSAL_SCHEDULER.md even if it does not appear newer.",
    )
    args = parser.parse_args()

    try:
        if args.export_current:
            path = write_universal_scheduler()
            print(f"Universal scheduler exported to {path}")
            return

        if args.write_template:
            path = write_universal_scheduler_template()
            print(f"Template written to {path}")
            return

        if args.check:
            validate_universal_scheduler()
            print(f"Universal scheduler looks valid: {UNIVERSAL_SCHEDULER_PATH}")
            return

        written_paths = compile_universal_scheduler(validate=True)
        print("Compiled universal scheduler into:")
        for path in written_paths:
            print(path)
    except UniversalSchedulerValidationError as exc:
        print_issue_report(exc)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Could not process {UNIVERSAL_SCHEDULER_PATH}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
