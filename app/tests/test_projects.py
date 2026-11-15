
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember


# Helper: register a user
def create_user(client, email):
    return client.post(
        "/users/",
        json={
            "name": "Test User",
            "email": email,
            "password": "test123456"
        }
    )


# Helper: login and get access token
def get_token(client, email):
    response = client.post(
        "/users/login",
        data={
            "username": email,
            "password": "test123456"
        }
    )
    return response.json()["access_token"]


# Helper: create a project
def create_project(client, token, name="Test Project"):
    return client.post(
        "/projects/",
        json={
            "name": name,
            "description": "Test project description"
        },
        headers={"Authorization": f"Bearer {token}"}
    )


# 1. Create project successfully
def test_create_project(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    response = create_project(client, token)

    assert response.status_code == 201
    assert response.json()["name"] == "Test Project"
    assert response.json()["owner_id"] == 1


# 2. Create project without authentication
def test_create_project_without_token(client):
    response = client.post(
        "/projects/",
        json={
            "name": "Test Project",
            "description": "Description"
        }
    )

    assert response.status_code == 401


# 3. Create project with missing name
def test_create_project_missing_name(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    response = client.post(
        "/projects/",
        json={"description": "Description"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422


# 4. Owner can see their projects
def test_owner_get_projects(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    create_project(client, token)

    response = client.get(
        "/projects/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


# 5. Owner can get one project
def test_get_single_project(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    project = create_project(client, token).json()

    response = client.get(
        f"/projects/{project['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == project["id"]


# 6. Unrelated user cannot access project
def test_unrelated_user_cannot_get_project(client):
    create_user(client, "owner@example.com")
    create_user(client, "other@example.com")

    owner_token = get_token(client, "owner@example.com")
    other_token = get_token(client, "other@example.com")

    project = create_project(client, owner_token).json()

    response = client.get(
        f"/projects/{project['id']}",
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403


# 7. Project member can access project
def test_member_can_get_project(client, db):
    create_user(client, "owner@example.com")
    create_user(client, "member@example.com")

    owner_token = get_token(client, "owner@example.com")
    member_token = get_token(client, "member@example.com")

    project = create_project(client, owner_token).json()

    member = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    db.add(
        ProjectMember(
            project_id=project["id"],
            user_id=member.id
        )
    )
    db.commit()

    response = client.get(
        f"/projects/{project['id']}",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 200


# 8. Member can see project in project list
def test_member_sees_project_in_list(client, db):
    create_user(client, "owner@example.com")
    create_user(client, "member@example.com")

    owner_token = get_token(client, "owner@example.com")
    member_token = get_token(client, "member@example.com")

    project = create_project(client, owner_token).json()

    member = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    db.add(
        ProjectMember(
            project_id=project["id"],
            user_id=member.id
        )
    )
    db.commit()

    response = client.get(
        "/projects/",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


# 9. Owner can update project using PUT
def test_update_project(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    project = create_project(client, token).json()

    response = client.put(
        f"/projects/{project['id']}",
        json={
            "name": "Updated Project",
            "description": "Updated description"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Project"


# 10. Owner can partially update project using PATCH
def test_patch_project(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    project = create_project(client, token).json()

    response = client.patch(
        f"/projects/{project['id']}",
        json={"name": "Patched Project"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Patched Project"
    assert response.json()["description"] == "Test project description"


# 11. Member cannot update project
def test_member_cannot_update_project(client, db):
    create_user(client, "owner@example.com")
    create_user(client, "member@example.com")

    owner_token = get_token(client, "owner@example.com")
    member_token = get_token(client, "member@example.com")

    project = create_project(client, owner_token).json()

    member = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    db.add(
        ProjectMember(
            project_id=project["id"],
            user_id=member.id
        )
    )
    db.commit()

    response = client.patch(
        f"/projects/{project['id']}",
        json={"name": "Unauthorized Update"},
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


# 12. Unrelated user cannot update project
def test_unrelated_user_cannot_update_project(client):
    create_user(client, "owner@example.com")
    create_user(client, "other@example.com")

    owner_token = get_token(client, "owner@example.com")
    other_token = get_token(client, "other@example.com")

    project = create_project(client, owner_token).json()

    response = client.patch(
        f"/projects/{project['id']}",
        json={"name": "Unauthorized Update"},
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403


# 13. Owner can delete project
def test_delete_project(client, db):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")

    project = create_project(client, token).json()

    response = client.delete(
        f"/projects/{project['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204

    deleted_project = db.query(Project).filter(
        Project.id == project["id"]
    ).first()

    assert deleted_project is None


# 14. Normal user cannot delete another user's project
def test_unrelated_user_cannot_delete_project(client):
    create_user(client, "owner@example.com")
    create_user(client, "other@example.com")

    owner_token = get_token(client, "owner@example.com")
    other_token = get_token(client, "other@example.com")

    project = create_project(client, owner_token).json()

    response = client.delete(
        f"/projects/{project['id']}",
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403


# 15. Admin can see all projects
def test_admin_can_see_all_projects(client, db):
    create_user(client, "owner@example.com")
    create_user(client, "admin@example.com")

    owner_token = get_token(client, "owner@example.com")

    create_project(client, owner_token)

    admin = db.query(User).filter(
        User.email == "admin@example.com"
    ).first()

    admin.role = "admin"
    db.commit()

    admin_token = get_token(client, "admin@example.com")

    response = client.get(
        "/projects/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
