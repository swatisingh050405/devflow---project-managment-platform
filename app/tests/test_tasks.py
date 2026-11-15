
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.project_member import ProjectMember


# ---------------- HELPERS ----------------

def create_user(client, email):
    return client.post(
        "/users/",
        json={
            "name": "Test User",
            "email": email,
            "password": "test123456"
        }
    )


def get_token(client, email):
    response = client.post(
        "/users/login",
        data={
            "username": email,
            "password": "test123456"
        }
    )
    return response.json()["access_token"]


def create_project(client, token):
    response = client.post(
        "/projects/",
        json={
            "name": "Test Project",
            "description": "Test description"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()


def create_task(client, project_id, token, **overrides):
    task_data = {
        "title": "Test Task",
        "description": "Test description",
        "status": "todo",
        "priority": "medium"
    }
    task_data.update(overrides)

    return client.post(
        f"/projects/{project_id}/tasks/",
        json=task_data,
        headers={"Authorization": f"Bearer {token}"}
    )


def add_member(db, project_id, email):
    user = db.query(User).filter(User.email == email).first()

    db.add(
        ProjectMember(
            project_id=project_id,
            user_id=user.id
        )
    )
    db.commit()

    return user


def setup_project(client):
    create_user(client, "owner@example.com")
    owner_token = get_token(client, "owner@example.com")

    project = create_project(client, owner_token)

    return project, owner_token


# ---------------- CREATE TASK ----------------

# 1. Owner can create task
def test_create_task(client):
    project, token = setup_project(client)

    response = create_task(client, project["id"], token)

    assert response.status_code == 201
    assert response.json()["title"] == "Test Task"
    assert response.json()["status"] == "todo"
    assert response.json()["priority"] == "medium"


# 2. Cannot create task without authentication
def test_create_task_without_token(client):
    project, _ = setup_project(client)

    response = client.post(
        f"/projects/{project['id']}/tasks/",
        json={"title": "Test Task"}
    )

    assert response.status_code == 401


# 3. Missing task title
def test_create_task_missing_title(client):
    project, token = setup_project(client)

    response = client.post(
        f"/projects/{project['id']}/tasks/",
        json={"description": "No title"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422


# 4. Invalid task status
def test_create_task_invalid_status(client):
    project, token = setup_project(client)

    response = create_task(
        client,
        project["id"],
        token,
        status="invalid"
    )

    assert response.status_code == 422


# 5. Invalid task priority
def test_create_task_invalid_priority(client):
    project, token = setup_project(client)

    response = create_task(
        client,
        project["id"],
        token,
        priority="urgent"
    )

    assert response.status_code == 422


# 6. Cannot assign task to non-existing user
def test_create_task_invalid_assignee(client):
    project, token = setup_project(client)

    response = create_task(
        client,
        project["id"],
        token,
        assignee_id=9999
    )

    assert response.status_code == 404


# 7. Cannot assign task to unrelated user
def test_create_task_assignee_not_member(client, db):
    project, token = setup_project(client)

    create_user(client, "other@example.com")

    other = db.query(User).filter(
        User.email == "other@example.com"
    ).first()

    response = create_task(
        client,
        project["id"],
        token,
        assignee_id=other.id
    )

    assert response.status_code == 400

   


# 8. Owner can assign task to project member
def test_create_task_assign_member(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    member = add_member(db, project["id"], "member@example.com")

    response = create_task(
        client,
        project["id"],
        owner_token,
        assignee_id=member.id
    )

    assert response.status_code == 201
    assert response.json()["assignee_id"] == member.id


# ---------------- GET TASKS ----------------

# 9. Owner can get all tasks
def test_get_tasks(client):
    project, token = setup_project(client)

    create_task(client, project["id"], token)
    create_task(client, project["id"], token, title="Second Task")

    response = client.get(
        f"/projects/{project['id']}/tasks/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


# 10. Owner can get one task
def test_get_single_task(client):
    project, token = setup_project(client)

    task = create_task(client, project["id"], token).json()

    response = client.get(
        f"/projects/{project['id']}/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == task["id"]


# 11. Non-existing task returns 404
def test_get_nonexistent_task(client):
    project, token = setup_project(client)

    response = client.get(
        f"/projects/{project['id']}/tasks/9999",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


# 12. Member can view project tasks
def test_member_can_get_tasks(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    member = add_member(db, project["id"], "member@example.com")
    member_token = get_token(client, "member@example.com")

    create_task(client, project["id"], owner_token)

    response = client.get(
        f"/projects/{project['id']}/tasks/",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


# ---------------- FILTERS ----------------

# 13. Filter tasks by status
def test_filter_tasks_by_status(client):
    project, token = setup_project(client)

    create_task(client, project["id"], token, title="Task 1", status="todo")
    create_task(client, project["id"], token, title="Task 2", status="done")

    response = client.get(
        f"/projects/{project['id']}/tasks/?task_status=done",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "done"


# 14. Filter tasks by priority
def test_filter_tasks_by_priority(client):
    project, token = setup_project(client)

    create_task(client, project["id"], token, priority="high")
    create_task(client, project["id"], token, title="Low Task", priority="low")

    response = client.get(
        f"/projects/{project['id']}/tasks/?priority=high",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["priority"] == "high"


# 15. Filter tasks by assignee
def test_filter_tasks_by_assignee(client, db):
    project, token = setup_project(client)

    create_user(client, "member@example.com")
    member = add_member(db, project["id"], "member@example.com")

    create_task(
        client,
        project["id"],
        token,
        assignee_id=member.id
    )
    create_task(client, project["id"], token, title="Unassigned Task")

    response = client.get(
        f"/projects/{project['id']}/tasks/?assignee_id={member.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["assignee_id"] == member.id


# ---------------- PAGINATION ----------------

# 16. Pagination using limit
def test_task_pagination_limit(client):
    project, token = setup_project(client)

    for i in range(5):
        create_task(
            client,
            project["id"],
            token,
            title=f"Task {i}"
        )

    response = client.get(
        f"/projects/{project['id']}/tasks/?limit=2",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


# 17. Pagination using skip
def test_task_pagination_skip(client):
    project, token = setup_project(client)

    for i in range(5):
        create_task(
            client,
            project["id"],
            token,
            title=f"Task {i}"
        )

    response = client.get(
        f"/projects/{project['id']}/tasks/?skip=2&limit=10",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 3


# ---------------- SORTING ----------------

# 18. Sort tasks by title ascending
def test_sort_tasks_by_title(client):
    project, token = setup_project(client)

    create_task(client, project["id"], token, title="Zebra")
    create_task(client, project["id"], token, title="Apple")

    response = client.get(
        f"/projects/{project['id']}/tasks/?sort_by=title&order=asc",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Apple"


# 19. Invalid sort field
def test_invalid_sort_field(client):
    project, token = setup_project(client)

    response = client.get(
        f"/projects/{project['id']}/tasks/?sort_by=invalid",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400


# 20. Invalid sort order
def test_invalid_sort_order(client):
    project, token = setup_project(client)

    response = client.get(
        f"/projects/{project['id']}/tasks/?order=random",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400


# ---------------- UPDATE TASK ----------------

# 21. Owner can fully update task
def test_update_task(client):
    project, token = setup_project(client)

    task = create_task(client, project["id"], token).json()

    response = client.put(
        f"/projects/{project['id']}/tasks/{task['id']}",
        json={
            "title": "Updated Task",
            "description": "Updated description",
            "status": "in_progress",
            "priority": "high",
            "assignee_id": None
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Task"
    assert response.json()["priority"] == "high"


# 22. Owner can partially update task
def test_patch_task_owner(client):
    project, token = setup_project(client)

    task = create_task(client, project["id"], token).json()

    response = client.patch(
        f"/projects/{project['id']}/tasks/{task['id']}",
        json={"priority": "high"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["priority"] == "high"


# 23. Assigned member can update task status
def test_member_can_update_assigned_task_status(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    member = add_member(db, project["id"], "member@example.com")
    member_token = get_token(client, "member@example.com")

    task = create_task(
        client,
        project["id"],
        owner_token,
        assignee_id=member.id
    ).json()

    response = client.patch(
        f"/projects/{project['id']}/tasks/{task['id']}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "done"


# 24. Member cannot update task priority
def test_member_cannot_update_task_priority(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    member = add_member(db, project["id"], "member@example.com")
    member_token = get_token(client, "member@example.com")

    task = create_task(
        client,
        project["id"],
        owner_token,
        assignee_id=member.id
    ).json()

    response = client.patch(
        f"/projects/{project['id']}/tasks/{task['id']}",
        json={"priority": "high"},
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


# 25. Member cannot update another member's task
def test_member_cannot_update_unassigned_task(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    add_member(db, project["id"], "member@example.com")
    member_token = get_token(client, "member@example.com")

    task = create_task(client, project["id"], owner_token).json()

    response = client.patch(
        f"/projects/{project['id']}/tasks/{task['id']}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


# ---------------- DELETE TASK ----------------

# 26. Owner can delete task
def test_delete_task(client, db):
    project, token = setup_project(client)

    task = create_task(client, project["id"], token).json()

    response = client.delete(
        f"/projects/{project['id']}/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204

    deleted_task = db.query(Task).filter(
        Task.id == task["id"]
    ).first()

    assert deleted_task is None


# 27. Member cannot delete task
def test_member_cannot_delete_task(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    add_member(db, project["id"], "member@example.com")
    member_token = get_token(client, "member@example.com")

    task = create_task(client, project["id"], owner_token).json()

    response = client.delete(
        f"/projects/{project['id']}/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403
