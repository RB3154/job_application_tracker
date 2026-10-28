"""Tests for /api/users."""

from conftest import PASSWORD, make_user, unique


# Signing up returns the new user's profile (never the password). There's no picture yet.
def test_signup_returns_private_profile(rudra):
    user, _ = rudra
    assert set(user) == {"id", "username", "email", "image_file", "image_path"}
    assert user["image_file"] is None
    assert user["image_path"] is None


# Signing up with a username that's already taken is refused with 409.
def test_signup_duplicate_username_conflicts(client, rudra):
    user, _ = rudra
    response = client.post(
        "/api/users", json={"username": user["username"], "email": f"{unique('x')}@test.com", "password": PASSWORD}
    )
    assert response.status_code == 409


# Emails are compared ignoring capital letters, so RUDRA@... counts as taken too.
def test_signup_duplicate_email_conflicts_ignoring_case(client, rudra):
    user, _ = rudra
    response = client.post(
        "/api/users", json={"username": unique("x"), "email": user["email"].upper(), "password": PASSWORD}
    )
    assert response.status_code == 409


# Logging in with the wrong password is refused with 401.
def test_login_with_wrong_password_fails(client, rudra):
    user, _ = rudra
    response = client.post("/api/users/token", data={"username": user["email"], "password": "wrong-password"})
    assert response.status_code == 401


# Anyone can view a profile, but it only shows id and username (no email).
def test_public_profile_hides_email(client, aman):
    user, _ = aman
    response = client.get(f"/api/users/{user['id']}")
    assert response.status_code == 200
    assert response.json() == {"id": user["id"], "username": user["username"], "image_file": None, "image_path": None}


# Viewing a user that doesn't exist gives 404.
def test_public_profile_of_unknown_user_is_404(client):
    assert client.get("/api/users/999999999").status_code == 404


# Opening /me without logging in must be refused with 401.
def test_me_requires_login(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


# A logged-in user gets their own full profile from /me.
def test_me_returns_own_profile(client, rudra):
    user, headers = rudra
    response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == user


# A user can change their username, but not to one that's already taken.
def test_update_me(client, rudra, aman):
    user, headers = rudra

    new_username = unique("renamed")
    response = client.patch("/api/users/me", json={"username": new_username}, headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == new_username

    taken = client.patch("/api/users/me", json={"username": aman[0]["username"]}, headers=headers)
    assert taken.status_code == 409

    # Put the original name back so other tests still see the same user.
    restored = client.patch("/api/users/me", json={"username": user["username"]}, headers=headers)
    assert restored.status_code == 200


# Editing /me without logging in is refused with 401.
def test_update_me_requires_login(client):
    assert client.patch("/api/users/me", json={"username": unique("x")}).status_code == 401


# After deleting your account, your old token stops working and your profile is gone.
def test_delete_me(client):
    user, headers = make_user(client, "temp")
    assert client.delete("/api/users/me", headers=headers).status_code == 204
    assert client.get("/api/users/me", headers=headers).status_code == 401
    assert client.get(f"/api/users/{user['id']}").status_code == 404
