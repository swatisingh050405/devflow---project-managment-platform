
from app.models.user import User
from app.models.project_member import ProjectMember


# ---------- HELPER FUNCTIONS ----------

def create_user(client, email):
    return client.post("/users/", json={
        "name": "Test User",
        "email": email,
        "password": "test123456"
    })


def get_token(client, email):
    response = client.post("/users/login", data={
        "username": email,
        "password": "test123456"
    })
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


def setup_project(client):
    create_user(client, "owner@example.com")
    token = get_token(client, "owner@example.com")
    project = create_project(client, token)
    return project, token


def add_member_directly(db, project_id, email):
    user = db.query(User).filter(
        User.email == email
    ).first()

    member = ProjectMember(
        project_id=project_id,
        user_id=user.id
    )

    db.add(member)
    db.commit()

    return user


# ---------- ADD MEMBER TESTS ----------

def test_owner_can_add_member(client, db):
    project, token = setup_project(client)

    create_user(client, "member@example.com")
    user = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    response = client.post(
        f"/projects/{project['id']}/members/",
        json={"user_id": user.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == user.id
    assert response.json()["project_id"] == project["id"]


def test_add_nonexistent_user(client):
    project, token = setup_project(client)

    response = client.post(
        f"/projects/{project['id']}/members/",
        json={"user_id": 9999},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_owner_cannot_add_themselves(client, db):
    project, token = setup_project(client)

    owner = db.query(User).filter(
        User.email == "owner@example.com"
    ).first()

    response = client.post(
        f"/projects/{project['id']}/members/",
        json={"user_id": owner.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400


def test_duplicate_member_not_allowed(client, db):
    project, token = setup_project(client)

    create_user(client, "member@example.com")

    user = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    url = f"/projects/{project['id']}/members/"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"user_id": user.id}

    first_response = client.post(
        url, json=data, headers=headers
    )

    second_response = client.post(
        url, json=data, headers=headers
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_add_member_without_token(client, db):
    project, token = setup_project(client)

    create_user(client, "member@example.com")
    user = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    response = client.post(
        f"/projects/{project['id']}/members/",
        json={"user_id": user.id}
    )

    assert response.status_code == 401


def test_unrelated_user_cannot_add_member(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "other@example.com")
    other_token = get_token(client, "other@example.com")

    create_user(client, "member@example.com")
    user = db.query(User).filter(
        User.email == "member@example.com"
    ).first()

    response = client.post(
        f"/projects/{project['id']}/members/",
        json={"user_id": user.id},
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403


# ---------- GET MEMBERS TESTS ----------

def test_owner_can_get_members(client, db):
    project, token = setup_project(client)

    create_user(client, "member@example.com")
    add_member_directly(db, project["id"], "member@example.com")

    response = client.get(
        f"/projects/{project['id']}/members/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_member_can_get_members(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    add_member_directly(db, project["id"], "member@example.com")

    member_token = get_token(client, "member@example.com")

    response = client.get(
        f"/projects/{project['id']}/members/",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 200


def test_unrelated_user_cannot_get_members(client):
    project, owner_token = setup_project(client)

    create_user(client, "other@example.com")
    other_token = get_token(client, "other@example.com")

    response = client.get(
        f"/projects/{project['id']}/members/",
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403


# ---------- REMOVE MEMBER TESTS ----------

def test_owner_can_remove_member(client, db):
    project, token = setup_project(client)

    create_user(client, "member@example.com")
    user = add_member_directly(
        db, project["id"], "member@example.com"
    )

    response = client.delete(
        f"/projects/{project['id']}/members/{user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204

    deleted_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project["id"],
        ProjectMember.user_id == user.id
    ).first()

    assert deleted_member is None


def test_remove_nonexistent_member(client):
    project, token = setup_project(client)

    response = client.delete(
        f"/projects/{project['id']}/members/9999",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_member_cannot_remove_other_member(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member1@example.com")
    add_member_directly(
        db, project["id"], "member1@example.com"
    )

    create_user(client, "member2@example.com")
    member2 = db.query(User).filter(
        User.email == "member2@example.com"
    ).first()

    add_member_directly(db, project["id"], "member2@example.com")

    member1_token = get_token(client, "member1@example.com")

    response = client.delete(
        f"/projects/{project['id']}/members/{member2.id}",
        headers={"Authorization": f"Bearer {member1_token}"}
    )

    assert response.status_code == 403


def test_unrelated_user_cannot_remove_member(client, db):
    project, owner_token = setup_project(client)

    create_user(client, "member@example.com")
    member = add_member_directly(
        db, project["id"], "member@example.com"
    )

    create_user(client, "other@example.com")
    other_token = get_token(client, "other@example.com")

    response = client.delete(
        f"/projects/{project['id']}/members/{member.id}",
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403
