
from app.models.user import User


# Helper: create a user
def create_test_user(client, email="test@example.com", password="test123456"):
    return client.post(
        "/users/",
        json={
            "name": "Test User",
            "email": email,
            "password": password
        }
    )


# Helper: login and get access token
def login_user(client, email="test@example.com", password="test123456"):
    response = client.post(
        "/users/login",
        data={
            "username": email,
            "password": password
        }
    )
    return response


# 1. Successful registration
def test_create_user(client, db):
    response = create_test_user(client)

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    assert user is not None
    assert user.hashed_password != "test123456"


# 2. Duplicate email registration
def test_duplicate_email(client):
    create_test_user(client)

    response = create_test_user(client)

    assert response.status_code == 409


# 3. Invalid email
def test_invalid_email(client):
    response = client.post(
        "/users/",
        json={
            "name": "Test User",
            "email": "invalid-email",
            "password": "test123456"
        }
    )

    assert response.status_code == 422


# 4. Missing required field
def test_missing_registration_field(client):
    response = client.post(
        "/users/",
        json={
            "name": "Test User",
            "email": "test@example.com"
        }
    )

    assert response.status_code == 422


# 5. Successful login
def test_login_success(client):
    create_test_user(client)

    response = login_user(client)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


# 6. Login with incorrect password
def test_login_wrong_password(client):
    create_test_user(client)

    response = login_user(
        client,
        password="wrongpassword"
    )

    assert response.status_code == 401


# 7. Get own profile
def test_get_my_profile(client):
    create_test_user(client)

    login_response = login_user(client)
    token = login_response.json()["access_token"]

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


# 8. Update own profile
def test_update_my_profile(client):
    create_test_user(client)

    token = login_user(client).json()["access_token"]

    response = client.patch(
        "/users/me",
        json={"name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


# 9. Update profile with an already registered email
def test_update_profile_duplicate_email(client):
    create_test_user(client, email="first@example.com")
    create_test_user(client, email="second@example.com")

    token = login_user(
        client,
        email="first@example.com"
    ).json()["access_token"]

    response = client.patch(
        "/users/me",
        json={"email": "second@example.com"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409


# 10. Change password successfully
def test_change_password(client):
    create_test_user(client)

    token = login_user(client).json()["access_token"]

    response = client.patch(
        "/users/me/password",
        json={
            "current_password": "test123456",
            "new_password": "newpassword123"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    # Old password should no longer work
    old_login = login_user(client)

    assert old_login.status_code == 401

    # New password should work
    new_login = login_user(
        client,
        password="newpassword123"
    )

    assert new_login.status_code == 200


# 11. Change password with incorrect current password
def test_change_password_wrong_current_password(client):
    create_test_user(client)

    token = login_user(client).json()["access_token"]

    response = client.patch(
        "/users/me/password",
        json={
            "current_password": "wrongpassword",
            "new_password": "newpassword123"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400


# 12. Access profile without authentication
def test_profile_without_token(client):
    response = client.get("/users/me")

    assert response.status_code == 401


# 13. Normal user cannot access all users
def test_get_all_users_forbidden(client):
    create_test_user(client)

    token = login_user(client).json()["access_token"]

    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


# 14. Admin can access all users
def test_admin_get_all_users(client, db):
    create_test_user(client)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    user.role = "admin"
    db.commit()

    token = login_user(client).json()["access_token"]

    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


# 15. Admin can delete a user
def test_admin_delete_user(client, db):
    create_test_user(client)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    user.role = "admin"
    db.commit()

    token = login_user(client).json()["access_token"]

    response = client.delete(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204

    deleted_user = db.query(User).filter(
        User.id == user.id
    ).first()

    assert deleted_user is None
