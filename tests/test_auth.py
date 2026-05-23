import pytest


VALID_USER = {"username": "testuser", "email": "test@example.com", "password": "secret123"}


class TestRegister:
    async def test_register_creates_user_and_returns_201(self, client):
        response = await client.post("/api/v1/auth/register", json=VALID_USER)
        assert response.status_code == 201
        body = response.json()
        assert body["username"] == VALID_USER["username"]
        assert body["email"] == VALID_USER["email"]
        assert body["is_active"] is True
        assert "id" in body
        assert "hashed_password" not in body

    async def test_register_duplicate_username_returns_409(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        dup = {"username": "testuser", "email": "other@example.com", "password": "secret123"}
        response = await client.post("/api/v1/auth/register", json=dup)
        assert response.status_code == 409
        assert response.json()["detail"] == "Username already taken"

    async def test_register_duplicate_email_returns_409(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        dup = {"username": "otheruser", "email": "test@example.com", "password": "secret123"}
        response = await client.post("/api/v1/auth/register", json=dup)
        assert response.status_code == 409
        assert response.json()["detail"] == "Email already registered"

    @pytest.mark.parametrize(
        "payload,field",
        [
            ({"username": "ab", "email": "a@b.com", "password": "secret123"}, "username"),
            ({"username": "validuser", "email": "a@b.com", "password": "12"}, "password"),
            ({"username": "validuser", "email": "x", "password": "secret123"}, "email"),
        ],
    )
    async def test_register_invalid_input_returns_422(self, client, payload, field):
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


class TestLogin:
    async def test_login_success_returns_token(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        response = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0

    async def test_login_wrong_password_returns_401(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        response = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "wrongpass"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    async def test_login_nonexistent_user_returns_401(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "secret123"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"


class TestGetMe:
    def _auth_header(self, token_response):
        token = token_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_get_me_returns_current_user(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        response = await client.get("/api/v1/auth/me", headers=self._auth_header(login_resp))
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "testuser"
        assert body["email"] == "test@example.com"

    async def test_get_me_without_token_returns_401(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_get_me_with_invalid_token_returns_401(self, client):
        response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication token"

    async def test_health_check_still_works(self, client):
        """Ensure existing health endpoint is unaffected."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestLogout:
    def _auth_header(self, token_response):
        token = token_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_logout_returns_204(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        response = await client.post("/api/v1/auth/logout", headers=self._auth_header(login_resp))
        assert response.status_code == 204

    async def test_revoked_token_cannot_access_me(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        headers = self._auth_header(login_resp)
        await client.post("/api/v1/auth/logout", headers=headers)
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has been revoked"

    async def test_logout_without_token_returns_401(self, client):
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401


class TestDeleteAccount:
    def _auth_header(self, token_response):
        token = token_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_delete_account_returns_204(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        response = await client.delete("/api/v1/auth/me", headers=self._auth_header(login_resp))
        assert response.status_code == 204

    async def test_cannot_access_after_deletion(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        headers = self._auth_header(login_resp)
        await client.delete("/api/v1/auth/me", headers=headers)
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    async def test_cannot_login_after_deletion(self, client):
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        headers = self._auth_header(login_resp)
        await client.delete("/api/v1/auth/me", headers=headers)
        response = await client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "secret123"}
        )
        assert response.status_code == 401

    async def test_delete_without_token_returns_401(self, client):
        response = await client.delete("/api/v1/auth/me")
        assert response.status_code == 401
