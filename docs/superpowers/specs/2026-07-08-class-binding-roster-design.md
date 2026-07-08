# Class Binding And Roster Registration Design

## Goal

Close the teacher/class/student registration loop for CodeSense: teachers bind existing classes with a class binding code, import a roster, and students register into the correct class by matching their student ID.

## Current Breakpoints

- Students can type any class name during registration, so the system may save `User.class_name` without a matching `User.class_id`.
- Teachers register successfully but receive no class ownership, while the teacher dashboard, class list, and assignment distribution all depend on `Class.teacher_id`.
- There is no student roster import path for teachers, so students cannot be pre-associated with an existing class before registration.

## Design

Use a class binding code instead of open teacher self-selection. Each existing `Class` owns a generated binding code. A teacher enters that code to bind the class if it is unassigned or already assigned to the same teacher. Teachers can later unbind their own classes. Admins can reset binding codes and still manually assign teachers through the existing class edit page.

Add a `StudentRoster` table for imported class lists. A roster row stores student ID, name, class, importer, and registration state. Importing a roster does not create accounts or passwords. If the student already exists, the import binds that existing student to the selected class. If the student does not exist, registration later matches the roster row by student ID and binds the new account to the roster class.

Student registration no longer trusts free-form class input. The backend requires a roster match for the submitted student ID. On match, it saves both `User.class_id` and `User.class_name`, marks the roster entry registered, and links it to the created user.

## Interfaces

- `Class.ensure_teacher_bind_code()` returns a valid binding code, creating one when missing.
- `Class.reset_teacher_bind_code()` replaces the binding code.
- `StudentRoster` stores imported students and registration status.
- `POST /classes/bind` binds the current teacher using a binding code.
- `POST /classes/<class_id>/unbind` unbinds a class from its current teacher.
- `POST /classes/<class_id>/reset-bind-code` resets a class binding code for admins.
- `POST /classes/<class_id>/import-students` imports an Excel or CSV roster for that class.

## Constraints

- Keep the current one-teacher-per-class model.
- Do not create student accounts during roster import.
- Use existing Flask, SQLAlchemy, Jinja, pandas, and Bootstrap patterns.
- Keep `User.class_name` synchronized with `User.class_id` for existing code paths that still filter by class name.
- Do not run automated tests in this implementation session; provide Anaconda test steps for the user.
