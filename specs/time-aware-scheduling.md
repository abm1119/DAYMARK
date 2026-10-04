# Time-aware task scheduling

## Problem

Tasks currently have planned dates but no time-of-day information, so a day view cannot order work against a daily timeline.

## Behavior

- A task may be unscheduled by time or have a complete start/end time slot.
- Time values use strict 24-hour `HH:MM` notation from `00:00` through `23:59`.
- A slot requires a planned date and both endpoints. End must be later than start; slots do not cross midnight.
- Two slots on the same date may not overlap. Adjacent slots are valid, and edits do not conflict with the task being edited.
- Recurring occurrences keep the same wall-clock slot on each occurrence date and are checked against existing tasks.
- Existing tasks remain valid and retain their existing dates and other task fields after migration.

## User experience

- Create/edit task forms offer clearly labeled 24-hour start and end fields.
- Day view orders timed tasks by start time and shows their time range; tasks without a slot appear in a distinct “Any time” group.
- The all-task view sorts by planned date and then slot while keeping its current status, category, and search filters.
- Task cards expose the slot consistently.
- The local task assistant can list, create, and update the same time fields.

## Validation coverage

Test existing-database migration, strict clock parsing, incomplete/reversed/date-less slots, overlap rejection and adjacent acceptance, task create/edit, recurring slots, assistant tool field handling, task ordering, and page rendering.
