# DevFlow --- Backend Engineering & Implementation Handbook

> **Purpose:** This is the permanent learning and revision guide for the
> DevFlow backend. It combines backend theory, the reasoning behind the
> design, the actual project architecture, implementation patterns, API
> flows, security decisions, testing guidance, and the remaining
> roadmap.
>
> **Documentation rule:** This file is a living document. Whenever a
> feature is completed, update its status, implementation notes, file
> paths, API behavior, and tests. Do not mark a feature complete merely
> because code was written; verify it through API/database tests.

------------------------------------------------------------------------

## 1. Project overview

### 1.1 What is DevFlow?

DevFlow is a project-management backend inspired by tools such as Linear
and Jira. It allows users to create projects, add members, create and
assign tasks, track task status and priority, and manage access
according to roles.

The project is also a practical backend-engineering learning exercise.
The objective is not just to make CRUD endpoints work. The objective is
to understand how a backend application is designed from request to
database and how it is secured, tested, deployed, and maintained.

### 1.2 Technology stack

  -----------------------------------------------------------------------
  Technology                          Role in DevFlow
  ----------------------------------- -----------------------------------
  Python                              Main programming language

  FastAPI                             HTTP API framework, routing,
                                      dependency injection and request
                                      validation

  PostgreSQL                          Relational database

  SQLAlchemy 2.x                      ORM: maps Python classes to
                                      database tables and builds SQL
                                      queries

  Alembic                             Database schema migration/version
                                      control

  Pydantic v2                         Request and response data
                                      validation/serialization

  PyJWT                               Signing and verifying JWTs

  pwdlib + Argon2                     Secure password hashing and
                                      verification

  pydantic-settings                   Loads application configuration
                                      from environment variables

  SMTP                                Sends password-reset emails
  -----------------------------------------------------------------------

Frontend integration, Docker, CI/CD, deployment and monitoring are later
roadmap items unless separately verified as completed.

### 1.3 Main domain concepts

-   **User:** An account that can log in and use the application.
-   **Project:** A workspace owned by one user.
-   **Project owner:** The user whose ID is stored in
    `projects.owner_id`.
-   **Project member:** A user represented by a row in
    `project_members`.
-   **Task:** A unit of work belonging to a project.
-   **Assignee:** The user responsible for a task. This is not
    necessarily the task creator.
-   **Admin:** A global user role with elevated access across projects
    and users.
-   **Access token:** Short-lived JWT sent with protected API requests.
-   **Refresh token:** Longer-lived token used to obtain a new access
    token.

### 1.4 High-level relationship

``` text
User
 ├── owns many Projects
 ├── joins Projects through ProjectMember
 ├── creates many Tasks
 └── may be assigned many Tasks

Project
 ├── has one Owner (User)
 ├── has many ProjectMembers
 └── contains many Tasks

Task
 ├── belongs to one Project
 ├── has one Creator (User)
 └── may have one Assignee (User)
```

A user can own a project without having a `project_members` row for that
project. Membership is represented separately.

------------------------------------------------------------------------

## 2. How a backend request works

Understanding this flow is more important than memorizing individual
FastAPI functions.

### 2.1 Request-to-response lifecycle

``` text
Client (browser / Postman / frontend)
        |
        | HTTP request: method + URL + headers + body
        v
FastAPI application
        |
        v
Router matches the method and path
        |
        v
Dependencies execute (authentication / authorization / DB session)
        |
        v
Pydantic validates request data
        |
        v
Endpoint executes business logic
        |
        v
SQLAlchemy queries or modifies PostgreSQL
        |
        v
Database returns rows / confirms transaction
        |
        v
Pydantic response schema serializes output
        |
        v
FastAPI returns HTTP response + status code
```

For a protected endpoint, authentication and authorization dependencies
run before the endpoint body. If a dependency raises an HTTP exception,
the endpoint body does not execute.

### 2.2 HTTP fundamentals

An HTTP request contains: - **Method:** what operation is requested
(`GET`, `POST`, `PUT`, `PATCH`, `DELETE`). - **Path:** which resource is
targeted. - **Headers:** metadata such as
`Authorization: Bearer <access-token>`. - **Body:** data sent to the
server, commonly JSON. - **Query parameters:** optional filters or
controls, such as `?skip=0&limit=10`.

Common status codes:

  Code   Meaning                 Typical DevFlow use
  ------ ----------------------- ----------------------------------------------
  200    OK                      Successful GET, PATCH or PUT
  201    Created                 User/project/task created
  204    No Content              Successful deletion
  400    Bad Request             Invalid query option or business input
  401    Unauthorized            Missing/invalid/expired authentication
  403    Forbidden               Authenticated user lacks permission
  404    Not Found               Resource does not exist or is not accessible
  409    Conflict                Duplicate email or membership
  422    Unprocessable Entity    Request validation failure
  500    Internal Server Error   Unexpected server-side failure

**401 vs 403:** 401 means valid authentication is absent. 403 means the
caller is authenticated but is not permitted to perform the operation.

### 2.3 REST and resource design

REST APIs expose resources through URLs. DevFlow resources include
users, projects, tasks and project members.

Examples: - `POST /projects/` --- create a project. - `GET /projects/`
--- list projects visible to the caller. - `GET /projects/12` ---
retrieve project 12. - `PATCH /projects/12` --- partially update project
12. - `DELETE /projects/12` --- delete project 12. -
`GET /projects/12/tasks/` --- list tasks belonging to project 12.

Use nouns for resource paths. Use HTTP methods to express the operation.

### 2.4 PUT vs PATCH

-   **PUT** generally replaces the resource representation. Required
    fields are normally supplied.
-   **PATCH** changes only selected fields. Unsent fields should remain
    unchanged.

In Pydantic v2, a common partial-update pattern is:

``` python
updates = payload.model_dump(exclude_unset=True)

for field, value in updates.items():
    setattr(db_object, field, value)
```

`exclude_unset=True` matters: it distinguishes fields omitted by the
client from fields explicitly supplied.

------------------------------------------------------------------------

## 3. Project architecture and file responsibilities

Current known structure:

``` text
devflow---project-managment-platform/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── users.py
│   │       ├── projects.py
│   │       ├── tasks.py
│   │       ├── project_members.py
│   │       └── auth.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── dependencies.py
│   │   └── email.py
│   ├── db/
│   │   └── session.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── task.py
│   │   ├── project_member.py
│   │   ├── refresh_token.py
│   │   └── password_reset_token.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── task.py
│   │   ├── project_member.py
│   │   └── auth.py
│   └── main.py
├── alembic/
├── .env                 # local secrets; must not be committed
├── .gitignore
└── README.md
```

The exact repository may contain additional files. Update this tree when
it changes.

### 3.1 Why separate these layers?

  -----------------------------------------------------------------------
  Layer                   Responsibility          Example
  ----------------------- ----------------------- -----------------------
  `api/routes`            HTTP endpoints and      `tasks.py`
                          request orchestration   

  `schemas`               Validate incoming data  `TaskCreate`,
                          and shape outgoing data `TaskResponse`

  `models`                Database table          `Task`
                          definitions and ORM     
                          relationships           

  `db`                    Engine, sessions and    `session.py`
                          declarative base        

  `core`                  Cross-cutting           JWT, settings,
                          application logic       dependencies, email

  `main.py`               Create FastAPI app and  `include_router()`
                          register routers        

  `alembic`               Versioned database      migration revisions
                          schema changes          
  -----------------------------------------------------------------------

A route should coordinate the operation, not contain every concern in
one place. For example, password hashing belongs in the security layer,
database columns belong in models, and request validation belongs in
schemas.

### 3.2 Application entry point

`app/main.py` creates the FastAPI application and registers routers.
Registering a router makes its endpoint definitions part of the
application.

Conceptual example:

``` python
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(project_members_router)
app.include_router(auth_router)
```

A router can define a prefix and tags:

``` python
router = APIRouter(
    prefix="/projects/{project_id}/tasks",
    tags=["Tasks"]
)
```

The prefix is combined with each endpoint path declared on that router.

------------------------------------------------------------------------

## 4. Configuration and database connection

### 4.1 Environment variables

`app/core/config.py` uses Pydantic Settings to read configuration:

``` python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
```

`.env` stores machine-specific configuration. It must be listed in
`.gitignore`. Never commit database passwords, SMTP app passwords or JWT
secrets.

### 4.2 SQLAlchemy engine and session

Known implementation in `app/db/session.py`:

``` python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Key concepts:

-   **Engine:** manages the connection pool and knows how to communicate
    with the database.
-   **Session:** represents a unit of work with the database; it tracks
    ORM objects and transactions.
-   **SessionLocal:** a factory that creates sessions.
-   **Base:** parent class for ORM models; its metadata describes the
    tables.
-   **`yield`:** provides the session to the endpoint/dependency and
    allows cleanup afterward.
-   **`finally`:** ensures the session is closed even if request
    processing fails.

Typical endpoint injection:

``` python
def some_endpoint(db: Session = Depends(get_db)):
    ...
```

FastAPI obtains a session for the request. Do not create a new engine or
session factory inside every endpoint.

### 4.3 Transactions

A transaction groups database changes into a unit of work.

Common write sequence:

``` python
db.add(record)
db.commit()
db.refresh(record)
```

-   `add()` stages the object in the session.
-   `commit()` persists the transaction.
-   `refresh()` reloads database-generated values, such as IDs or
    timestamps.

If a database operation fails during a transaction, use `db.rollback()`
before reusing the session. A commit should happen only after the
operation's validation and business rules have passed.

------------------------------------------------------------------------

## 5. SQLAlchemy ORM and relational modelling

### 5.1 Model vs schema

These are different:

-   **SQLAlchemy model:** describes how data is stored in the database.
-   **Pydantic schema:** describes what data the API accepts or returns.

For example, a User model has `hashed_password`, but a public
`UserResponse` schema must not expose it.

### 5.2 Main tables

The following describes the known design. Check the actual model files
for the authoritative column definitions.

#### `users`

-   `id` --- primary key.
-   `name`
-   `email` --- unique and indexed.
-   `role` --- global role, currently constrained to `user` or `admin`;
    default `user`.
-   `hashed_password`
-   `is_active`
-   `created_at`

#### `projects`

-   `id` --- primary key.
-   `name`
-   `description`
-   `owner_id` --- foreign key to `users.id`.
-   `created_at`

#### `tasks`

-   `id` --- primary key.
-   `title`
-   `description`
-   `status` --- constrained to `todo`, `in_progress`, `done`.
-   `priority` --- constrained to `low`, `medium`, `high`.
-   `project_id` --- foreign key to `projects.id`, with cascade delete.
-   `assignee_id` --- nullable foreign key to `users.id`, with
    `SET NULL` on user deletion.
-   `created_by_id` --- foreign key to `users.id`.
-   `created_at`

#### `project_members`

-   `id`
-   `project_id` --- foreign key to projects, cascade delete.
-   `user_id` --- foreign key to users, cascade delete.
-   `role` --- currently defaults to `member`.
-   `joined_at`
-   Unique constraint on `(project_id, user_id)`.

#### `refresh_tokens`

-   `id`
-   `user_id`
-   `jti` --- unique token identifier.
-   `expires_at`
-   `revoked`
-   `created_at`

#### `password_reset_tokens`

-   `id`
-   `user_id`
-   `token_hash` --- unique hash of the raw reset token.
-   `expires_at`
-   `used`
-   `created_at`

### 5.3 Primary keys, foreign keys and constraints

-   A **primary key** uniquely identifies a row.
-   A **foreign key** links a row to another table and enforces
    referential integrity.
-   A **unique constraint** prevents duplicate values or combinations.
-   A **check constraint** restricts a column to allowed values.
-   `ON DELETE CASCADE` deletes dependent rows when the referenced row
    is deleted.
-   `ON DELETE SET NULL` preserves the dependent row but clears its
    reference.

Constraints should enforce important data rules at the database level as
well as in application code. Application validation gives useful API
errors; database constraints protect data integrity even if another code
path writes to the database.

### 5.4 ORM relationships and foreign keys

A SQLAlchemy `relationship()` is an ORM-level way to navigate related
objects. It is not itself a database foreign-key column.

The Task model has two references to User: - `assignee_id` -
`created_by_id`

Because both point to the same table, relationships must specify the
correct `foreign_keys` field. Otherwise SQLAlchemy may not know which
foreign key a relationship represents.

------------------------------------------------------------------------

## 6. Pydantic schemas and validation

Schemas define the API contract.

Typical schema responsibilities: - `UserCreate`: fields accepted during
registration. - `UserResponse`: safe fields returned to the client. -
`ProjectCreate` / `ProjectResponse`: project input/output. -
`TaskCreate` / `TaskUpdate` / `TaskResponse`: task input/output. -
`ForgotPasswordRequest` / `ResetPasswordRequest`: password-reset
payloads.

With Pydantic v2, ORM response serialization commonly uses:

``` python
from pydantic import BaseModel, ConfigDict

class SomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

This allows Pydantic to read attributes from SQLAlchemy ORM objects.

**Security rule:** Never accept privileged fields such as `role`,
`owner_id`, `created_by_id` or `hashed_password` directly from an
untrusted client unless there is a deliberate, authorized administrative
workflow. In DevFlow, registration/profile schemas intentionally do not
let users set their own global role.

------------------------------------------------------------------------

## 7. Authentication: passwords and JWT

### 7.1 Authentication vs authorization

-   **Authentication:** verifies who is making the request.
-   **Authorization:** checks what that authenticated user is allowed to
    do.

A valid JWT proves that the token was signed by the application and has
not expired. It does not automatically mean the user can access every
resource.

### 7.2 Password hashing

Passwords must not be stored in plaintext or reversibly encrypted for
normal login.

DevFlow uses Argon2 through `pwdlib`:

``` python
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)
```

Hashing is one-way. During login, the submitted password is verified
against the stored hash; the original password is not recovered.

### 7.3 JWT structure

A JWT has three encoded sections:

``` text
header.payload.signature
```

The payload can contain claims such as: - `sub` --- subject, used here
for the user ID. - `exp` --- expiry timestamp. - `type` ---
application-specific token type (`access` or `refresh`). - `jti` ---
unique token identifier for refresh-token tracking.

Do not put passwords, secrets or sensitive personal data in a JWT
payload. JWT payloads are encoded, not encrypted.

### 7.4 Access token flow

1.  User submits login credentials.
2.  Backend looks up the user by email.
3.  Backend verifies the password hash.
4.  Backend creates a short-lived access token.
5.  Backend returns the access token.
6.  Client sends it in the `Authorization: Bearer <token>` header.
7.  `get_current_user` decodes and validates it, checks token type,
    extracts the user ID, loads the user and checks that the account is
    active.

The current OAuth2 scheme in the project declares
`tokenUrl="/users/login"`. Login uses `OAuth2PasswordRequestForm`, where
the `username` form field carries the email address.

### 7.5 Refresh-token flow

Access tokens are short-lived. Refresh tokens allow the client to obtain
a new access token without asking the user to log in again.

Known DevFlow design:

1.  Login creates an access token and a refresh token.
2.  Refresh token has a unique `jti` and expiry.
3.  The refresh-token session is stored in `refresh_tokens`.
4.  Refresh token is set in an HttpOnly cookie with path `/auth`.
5.  `POST /auth/refresh` validates the cookie JWT, token type, subject
    and `jti`.
6.  Backend checks the matching database session, revocation state and
    expiry.
7.  The old refresh session is revoked.
8.  A new access token and refresh token are issued; the new refresh
    session is stored.

This is **refresh-token rotation**. Keeping revoked records provides a
server-side record that a token has already been used/revoked and helps
prevent replay.

### 7.6 Logout

`POST /auth/logout` attempts to revoke the refresh-token session and
clears the refresh cookie.

Important limitation in the current design: logout revokes the refresh
token, but an already-issued access token remains usable until its
expiry unless access-token revocation/denylisting is separately
implemented. The access token is short-lived to limit this window.

### 7.7 Cookie security

The current development cookie configuration uses `httponly=True`,
`secure=False`, `samesite="lax"`, and path `/auth`.

Before production: - Set `secure=True` when serving over HTTPS. - Review
`SameSite` and CORS/CSRF requirements for the actual frontend
deployment. - Keep refresh tokens out of browser JavaScript by using
HttpOnly cookies. - Ensure cookie path/domain and frontend origin are
correct. - Do not treat `secure=False` as a production setting.

------------------------------------------------------------------------

## 8. Password reset flow

Known implementation:

### Forgot password

`POST /auth/forgot-password`

1.  Accept email address.
2.  Return a generic response whether or not the account exists, to
    reduce account enumeration.
3.  Invalidate previous unused reset tokens for that user.
4.  Generate a random token using `secrets.token_urlsafe(32)`.
5.  Hash the raw token with SHA-256.
6.  Store only the hash, expiry and used state in
    `password_reset_tokens`.
7.  Email a frontend reset link containing the raw token.
8.  Use FastAPI `BackgroundTasks` to schedule email delivery after the
    response.

### Reset password

`POST /auth/reset-password`

1.  Receive reset token and new password.
2.  Hash the supplied token.
3.  Find the matching unused token record.
4.  Check expiry and user.
5.  Hash and save the new password.
6.  Mark reset token as used.
7.  Revoke the user's existing refresh sessions.
8.  Commit the changes.

The reset token is time-limited (15 minutes in the implemented design)
and one-time use.

**Testing note:** SMTP delivery and the complete frontend link flow
still need explicit end-to-end verification. Do not assume email
delivery works merely because the endpoint code exists.

------------------------------------------------------------------------

## 9. FastAPI dependency injection

FastAPI dependencies are reusable functions that provide values or
enforce preconditions for endpoints.

Example:

``` python
def endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ...
```

FastAPI executes the dependencies and injects their return values.

In DevFlow: - `get_db` provides a database session. - `get_current_user`
authenticates the request. - `require_admin` checks the global admin
role. - `require_project_owner` checks ownership of a specific project
(with admin bypass in the current intended design). -
`require_project_member` checks whether the user is admin, owner or a
project member.

A dependency function does not protect an endpoint merely because it
exists. It must be attached using `Depends(...)` (or router-level
dependencies).

Conceptual example:

``` python
@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    ...
```

If `require_admin` raises 403, the endpoint body does not run.

### 9.1 Current RBAC design

Global role: - `admin` - `user`

Project-level access: - Owner is determined by `projects.owner_id`. -
Member is determined by a `project_members` row. - A normal user who is
neither owner nor member should not access that project. - Admin should
have global access.

Do not confuse global role with project membership. A user can be a
normal global user and still own or belong to several projects.

### 9.2 RBAC implementation status

  -----------------------------------------------------------------------
  Item                                Status
  ----------------------------------- -----------------------------------
  Add `users.role` with allowed       Implemented and migrated
  values and default                  

  `require_admin` dependency          Added

  `require_project_owner` dependency  Added/in progress; verify current
                                      file

  `require_project_member` dependency Added/in progress; verify current
                                      file

  Apply dependencies consistently to  Not yet completed
  project routes                      

  Apply permissions to task routes    Pending

  Apply permissions to                Pending
  member-management routes            

  Protect admin-only user-management  Pending
  routes                              

  Test                                Pending
  admin/owner/member/unrelated-user   
  scenarios                           
  -----------------------------------------------------------------------

**Permission policy to implement and verify:**

  ---------------------------------------------------------------------------
  Operation                Admin          Owner         Member Unrelated user
  --------------- -------------- -------------- -------------- --------------
  View all                   Yes     Own/member     Own/member             No
  projects                             projects       projects 

  View a project             Yes            Yes            Yes             No

  Update/delete              Yes            Yes             No             No
  project                                                      

  Manage project             Yes            Yes             No             No
  members                                                      

  View project               Yes            Yes            Yes             No
  tasks                                                        
  ---------------------------------------------------------------------------

Member task-edit permissions must be explicitly decided before
implementing them. A sensible initial policy is that a member can update
tasks assigned to them, while only an owner/admin can create, assign, or
delete tasks. Confirm this policy against the intended product behavior.

Important implementation detail: if a route uses `require_project_owner`
but its database query still filters `owner_id == current_user.id`,
admin bypass will be defeated by that extra filter. Authorization
dependencies and resource queries must agree.

------------------------------------------------------------------------

## 10. DevFlow API inventory

This is the known route inventory from the implementation history.
Confirm exact HTTP methods, trailing slashes, response models and status
codes against the current route files and Swagger docs (`/docs`).

### Users --- `/users`

  ----------------------------------------------------------------------------
  Endpoint                     Purpose                 Known status
  ---------------------------- ----------------------- -----------------------
  `POST /users/`               Register                Implemented

  `GET /users/`                List users              Implemented;
                                                       authorization needs
                                                       review

  `DELETE /users/{user_id}`    Delete user             Implemented; admin-only
                                                       protection pending

  `POST /users/login`          Login and issue tokens  Implemented

  `GET /users/me`              Get current profile     Implemented

  `PATCH /users/me`            Update profile          Implemented

  `PATCH /users/me/password`   Change password         Implemented
  ----------------------------------------------------------------------------

### Projects --- `/projects`

  -----------------------------------------------------------------------
  Operation               Purpose                 Known status
  ----------------------- ----------------------- -----------------------
  Create                  Create project; creator Implemented
                          becomes owner           

  List                    List projects           Implemented; current
                                                  owner-only filtering
                                                  needs RBAC expansion

  Get by ID               Retrieve one project    Implemented

  PUT/PATCH               Update project          Implemented

  Delete                  Delete project          Implemented
  -----------------------------------------------------------------------

### Tasks --- `/projects/{project_id}/tasks`

  Operation        Purpose             Known status
  ---------------- ------------------- --------------
  POST             Create task         Implemented
  GET              List/filter tasks   Implemented
  GET by task ID   Retrieve task       Implemented
  PUT/PATCH        Update task         Implemented
  DELETE           Delete task         Implemented

Task list supports: - `task_status` - `priority` - `assignee_id` -
`skip` - `limit` - `sort_by` (`created_at`, `priority`, `title`) -
`order` (`asc`, `desc`)

The query is built by applying filters, then sorting, then pagination,
then executing `.all()`. Invalid sort fields/order return 400 in the
current design.

### Project members --- `/projects/{project_id}/members`

  Operation   Purpose         Known status
  ----------- --------------- --------------
  POST        Add member      Implemented
  GET         List members    Implemented
  DELETE      Remove member   Implemented

Current membership logic checks that the project and user exist,
prevents duplicate membership, and prevents adding the owner as a
member. RBAC must be applied consistently, including admin behavior.

### Authentication --- `/auth`

  ------------------------------------------------------------------------------
  Endpoint                       Purpose                 Known status
  ------------------------------ ----------------------- -----------------------
  `POST /auth/refresh`           Rotate refresh token    Implemented
                                 and issue new access    
                                 token                   

  `POST /auth/logout`            Revoke refresh session  Implemented
                                 and clear cookie        

  `POST /auth/forgot-password`   Generate reset token    Implemented
                                 and schedule email      

  `POST /auth/reset-password`    Validate reset token    Implemented
                                 and change password     
  ------------------------------------------------------------------------------

------------------------------------------------------------------------

## 11. Business logic and validation

A working endpoint is not necessarily a correct endpoint. Business rules
protect the domain.

Examples already implemented or planned in DevFlow:

-   Email must be unique.
-   A task must belong to an existing project.
-   An assignee must exist.
-   An assignee must be the project owner or a member of that project.
-   A project owner cannot be added as their own project member.
-   A project/user membership pair must be unique.
-   Task status and priority must use allowed values.
-   A user cannot assign themselves an admin role through
    registration/profile update.
-   Only permitted users may read or modify a project and its tasks.

Validation should occur at multiple layers: 1. Pydantic validates
request shape and types. 2. Route/service business logic validates
domain rules. 3. Database constraints protect data integrity.

Do not rely on frontend validation for security or correctness.

------------------------------------------------------------------------

## 12. Filtering, sorting and pagination

These are common backend API features used when a table can contain many
records.

### Filtering

Filtering reduces the result set based on criteria.

Example: - only tasks with `status="todo"` - only tasks with
`priority="high"` - only tasks assigned to user 7

### Sorting

Sorting defines result order. DevFlow currently supports `created_at`,
`priority` and `title`, with ascending or descending order.

Never pass arbitrary client-provided strings directly into SQL
expressions. Map allowed sort keys to known model columns and reject
unknown keys.

### Pagination

Offset pagination uses: - `skip`: number of rows to skip. - `limit`:
maximum number of rows returned.

Example: `skip=20&limit=10` requests the third page when page size is
10.

Production hardening: - enforce a maximum `limit`; - validate
non-negative `skip`; - use stable ordering (add a unique tie-breaker
such as `id`); - consider cursor pagination for very large/changing
datasets.

------------------------------------------------------------------------

## 13. Database migrations with Alembic

A model change does not automatically change an existing PostgreSQL
table.

Migration workflow:

``` powershell
uv run alembic revision --autogenerate -m "describe schema change"
uv run alembic upgrade head
```

-   `revision --autogenerate` compares SQLAlchemy metadata with the
    database and generates a migration proposal.
-   Review the generated migration before applying it.
-   `upgrade head` applies migrations up to the latest revision.
-   Migrations preserve a history of schema changes across environments.

Autogenerate is not infallible. Always inspect the generated `upgrade()`
and `downgrade()` functions. Confirm that all models are imported into
the metadata used by Alembic; otherwise changes may be missed.

Known migrations include the core tables, project members, refresh
tokens, password-reset tokens and the `users.role` column.

------------------------------------------------------------------------

## 14. Security checklist

Before calling the backend production-ready, review:

-   Passwords are hashed with Argon2; plaintext is never stored or
    logged.
-   Secrets and database credentials are in environment variables.
-   `.env` is excluded from Git.
-   Access tokens have expiry and token-type checks.
-   Refresh tokens are tracked, rotated and revocable.
-   Reset tokens are hashed in storage, expire and are one-time use.
-   Registration/profile schemas cannot set global role.
-   Every protected endpoint has appropriate authorization.
-   Resource queries do not leak another user's data.
-   User-supplied sort fields are allowlisted.
-   Database constraints enforce uniqueness and allowed values.
-   Error responses do not expose stack traces or secrets.
-   CORS is restricted to intended frontend origins.
-   Cookies use HTTPS-only settings in production.
-   Rate limiting is considered for login and password-reset endpoints.
-   Logs do not contain passwords, raw reset tokens or bearer tokens.
-   Destructive operations and ownership transfer have explicit rules.
-   Dependency versions are pinned/managed and security updates are
    reviewed.

This is a review checklist, not a claim that every item is already
implemented.

------------------------------------------------------------------------

## 15. Testing strategy

Automated testing is a planned next phase after RBAC.

### 15.1 What to test

**Unit tests** - Password hashing and verification. - Token
creation/decoding helpers. - Pure validation/business-rule functions.

**API/integration tests** - Registration success and duplicate email. -
Login success and wrong password. - Protected endpoint without token
(401). - Invalid/expired token (401). - User profile update. - Project
creation and ownership. - Task creation and invalid assignee. -
Duplicate project membership. - Refresh-token rotation and reuse
rejection. - Logout revocation. - Password reset expiry and one-time
use. - RBAC matrix for admin, owner, member and unrelated user.

### 15.2 RBAC test matrix

Create separate test accounts: - Admin A - Owner B - Member C -
Unrelated user D

Create a project owned by B and add C as a member. Then verify:

  -----------------------------------------------------------------------
  Test                                Expected
  ----------------------------------- -----------------------------------
  A reads B's project                 Allowed

  B reads B's project                 Allowed

  C reads B's project                 Allowed

  D reads B's project                 Denied

  C deletes B's project               Denied

  B removes C                         Allowed

  C adds D as member                  Denied

  A manages members                   Allowed, if admin management policy
                                      is implemented

  User attempts to register with      Role must not be accepted/set
  `role=admin`                        
  -----------------------------------------------------------------------

Test both success and failure cases. A 200 response alone is not
sufficient; inspect database state when testing writes.

### 15.3 Test tools and setup (planned)

Likely stack: - `pytest` - FastAPI `TestClient` or HTTPX - A dedicated
test database - Fixtures for database session, users, projects and auth
tokens

Do not run destructive tests against the development/production
database. Tests should isolate data and clean up after themselves.

------------------------------------------------------------------------

## 16. Deployment and operations roadmap

These are future implementation topics, not completed features.

### Docker

Package the application and its dependencies into a reproducible
container. Learn: - Dockerfile - image vs container - ports -
environment variables - volumes - Docker Compose for API + PostgreSQL

### CI/CD

Use GitHub Actions to automate: 1. dependency installation; 2.
linting/format checks; 3. automated tests; 4. build checks; 5.
deployment after successful checks.

### Deployment

Deploy the API and PostgreSQL using suitable hosting. Configure: -
production `DATABASE_URL`; - strong `SECRET_KEY`; - HTTPS; - CORS; -
secure cookies; - migrations; - health checks; - backups.

### Logging and monitoring

Add structured logs, request/error visibility, health endpoints and
monitoring. Never log secrets or authentication tokens.

### Further backend features

After core reliability: - file uploads and storage; - background jobs
for email/long-running work; - audit logs for sensitive actions; -
notification system; - caching/Redis where justified; - WebSockets for
real-time updates where justified.

Do not add technologies merely to make the stack look larger. Add them
when the product requirement needs them.

------------------------------------------------------------------------

## 17. How to run and inspect the project

Run commands from the repository root unless the command specifically
requires another directory.

Typical development server command (confirm the actual import path in
the current repository):

``` powershell
uv run uvicorn app.main:app --reload
```

If the project currently uses a different module path, use the path that
matches the actual `main.py` location.

Useful URLs: - Swagger UI: `http://127.0.0.1:8000/docs` - OpenAPI JSON:
`http://127.0.0.1:8000/openapi.json`

Database migration commands:

``` powershell
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic current
uv run alembic history
```

Use the PostgreSQL executable directly if `psql` is not on PATH (adjust
version/path if installation differs):

``` powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" --version
```

Never paste real credentials into screenshots, source control or shared
documentation.

------------------------------------------------------------------------

## 18. Interview revision: questions you should be able to answer

Use these as prompts. First answer without looking; then explain where
the concept appears in DevFlow.

### HTTP, REST and FastAPI

1.  What happens from the moment a client sends a request until it
    receives a response?
2.  What is the difference between GET, POST, PUT, PATCH and DELETE?
3.  What is the difference between path parameters, query parameters,
    headers and request bodies?
4.  What is REST? Why are resources represented as nouns?
5.  What is the difference between 401, 403, 404, 409 and 422?
6.  What is dependency injection? How does FastAPI's `Depends()` work?
7.  What is the purpose of a router and `include_router()`?

### Python and application structure

8.  Why separate routes, schemas, models and core logic?
9.  What does a generator using `yield` do in `get_db()`?
10. Why use `try/finally` to close a database session?
11. What is the difference between synchronous and asynchronous
    endpoints? Is using `async def` automatically faster?
12. Why should configuration and secrets not be hardcoded?

### SQL and SQLAlchemy

13. What are primary keys and foreign keys?
14. What is referential integrity?
15. What is the difference between a database constraint and application
    validation?
16. What is an ORM? What does SQLAlchemy map?
17. What is the difference between a SQLAlchemy model and a Pydantic
    schema?
18. What do `db.add()`, `db.commit()`, `db.refresh()` and
    `db.rollback()` do?
19. What is a transaction?
20. What is the difference between a foreign key and an ORM
    relationship?
21. Why does Task need to identify which foreign key is used for its
    creator and assignee relationships?
22. What do CASCADE and SET NULL mean?
23. Why use Alembic if SQLAlchemy models already define tables?

### Authentication and security

24. What is authentication vs authorization?
25. Why hash passwords instead of encrypting or storing them?
26. What is a salt? Why is a password hash deliberately expensive to
    compute?
27. What is a JWT? What are its header, payload and signature?
28. Is a JWT payload encrypted? What should never be placed in it?
29. What are `sub`, `exp` and `jti`?
30. Why use short-lived access tokens and longer-lived refresh tokens?
31. What is refresh-token rotation? How does the database help revoke a
    refresh token?
32. Why does logout not necessarily invalidate an already-issued access
    JWT?
33. Why store a hash of a password-reset token instead of the raw token?
34. Why should forgot-password return a generic response?
35. What is RBAC? How is a global role different from project
    membership?
36. Why must the server enforce authorization even if the frontend hides
    buttons?

### API design and performance

37. What are filtering, sorting and pagination?
38. Why should sort fields be allowlisted?
39. What is offset pagination? What problems can it have?
40. What is the N+1 query problem?
41. What is an index? What are its benefits and costs?
42. Why should database queries filter by the caller's access rights?

### Testing and deployment

43. What is the difference between unit, integration and end-to-end
    tests?
44. Why should tests use a separate database?
45. What is a fixture in pytest?
46. What problem does Docker solve?
47. What is the difference between an image and a container?
48. What is CI/CD?
49. Why should migrations run as part of deployment?
50. What should be monitored in a production API?

### How to make an answer interview-ready

For each question, prepare three parts: 1. **Definition:** explain the
concept in two or three sentences. 2. **Reason:** explain why a backend
needs it. 3. **DevFlow example:** name the file, endpoint or flow where
you implemented it.

Example --- dependency injection: - Definition: FastAPI dependencies are
reusable callables whose results are injected into endpoint
parameters. - Reason: They centralize shared setup and checks, such as
database sessions and authentication. - DevFlow example: `get_db`
provides the SQLAlchemy session; `get_current_user` validates the access
token; RBAC dependencies will enforce project/admin permissions.

------------------------------------------------------------------------

## 19. Current project status and next actions

### Completed / implemented according to the development history

-   [x] FastAPI application and router structure
-   [x] PostgreSQL connection and SQLAlchemy setup
-   [x] User, Project and Task models
-   [x] ProjectMember model and membership APIs
-   [x] Pydantic request/response schemas
-   [x] Alembic migrations for core and added tables
-   [x] User registration and password hashing
-   [x] Login and access-token authentication
-   [x] Refresh-token persistence, rotation and revocation
-   [x] Logout endpoint
-   [x] Forgot-password and reset-password logic
-   [x] User profile read/update and password update
-   [x] Project CRUD
-   [x] Task CRUD and assignment validation
-   [x] Task filtering, sorting and pagination
-   [x] Global `users.role` column and migration
-   [x] Initial authorization dependency functions added/in progress

### Immediate next phase: finish RBAC

1.  Review the actual current `app/core/dependencies.py`.
2.  Review `app/api/routes/projects.py`.
3.  Attach project-member checks to project read endpoints.
4.  Attach owner/admin checks to project update/delete and
    membership-management endpoints.
5.  Make project listing return all projects for admins and owned/member
    projects for normal users.
6.  Apply task read/write permissions and define member task-edit rules.
7.  Protect user administration endpoints with `require_admin`.
8.  Test the complete role/permission matrix.
9.  Update this handbook with the final implemented policy and exact
    endpoint behavior.

### Then continue

10. Add automated tests with pytest and a separate test database.
11. Improve validation, error handling and security hardening.
12. Review indexes, query efficiency and transaction boundaries.
13. Add Docker and Docker Compose.
14. Add GitHub Actions CI.
15. Deploy the API and database.
16. Add logging, monitoring and operational documentation.

------------------------------------------------------------------------

## 20. How to use this handbook after a long break

When returning to DevFlow after weeks or months:

1.  Read Sections 1--3 to recover the project purpose, architecture and
    request lifecycle.
2.  Read Sections 4--9 to revise database, ORM, schemas, authentication
    and dependencies.
3.  Read Section 10 to remember the API surface.
4.  Read Sections 11--16 to revise business logic, security, testing and
    deployment.
5.  Read Section 19 to identify the next unfinished task.
6.  Open the referenced source files and trace one request end-to-end.
7.  Run the app and use `/docs` to test the endpoint.

For any feature, trace this chain:

``` text
Route
  -> dependencies
  -> Pydantic request schema
  -> business validation
  -> SQLAlchemy model/query
  -> PostgreSQL transaction
  -> Pydantic response schema
  -> HTTP status/response
```

### Documentation maintenance template

Add this block whenever a new feature is completed:

``` text
Feature:
Requirement / problem:
Files changed:
New or changed endpoints:
Request schema:
Response schema:
Database/model changes:
Migration:
Authorization rule:
Business validation:
Request-to-database flow:
Important code pattern:
Error cases and status codes:
How manually tested:
Automated tests:
Known limitations:
Interview concepts learned:
```

------------------------------------------------------------------------

## 21. Accuracy and scope note

This handbook is based on the DevFlow implementation history available
during its preparation. It is a project-specific learning guide, not a
live inspection of every current source file. Exact route signatures,
response models, migration names, dependency attachment, SMTP behavior
and test coverage must be confirmed against the current repository.

Where this handbook says **pending**, **in progress**, **verify**, or
**planned**, do not describe that feature as complete in an interview.
Update the document as implementation and testing progress.

**The source code remains the final authority for what the application
currently does.**
