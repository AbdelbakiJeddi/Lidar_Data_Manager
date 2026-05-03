# Implementation Plan - Role-Based Access Control (RBAC)

This plan outlines the steps to introduce two distinct user roles: **Admin** and **Regular User**. Admins will have full management capabilities (upload, process, delete), while Regular Users will be restricted to viewing and extracting data.

## User Review Required

> [!IMPORTANT]
> This implementation will introduce **Authentication**. Users will need to log in to access the system. For the initial phase, we will use a simple Login screen with hardcoded roles or a local database for users.

> [!WARNING]
> Existing API endpoints will be protected. Any external scripts using these APIs will need to be updated to include a JWT token in the headers.

## Proposed Changes

### Backend (FastAPI)

#### [NEW] [user.py](file:///home/abok/Desktop/pcd_ws/project/app/models/user.py)
- Define `UserRole` Enum (`ADMIN`, `USER`).
- Define `User` and `UserCreate` Pydantic models.
- Define `Token` and `TokenData` models for JWT.

#### [NEW] [auth_utils.py](file:///home/abok/Desktop/pcd_ws/project/app/core/auth_utils.py)
- Implement password hashing using `passlib`.
- Implement JWT token creation and validation using `python-jose`.

#### [NEW] [auth.py](file:///home/abok/Desktop/pcd_ws/project/app/api/auth.py)
- Create `/auth/login` endpoint to exchange credentials for a JWT.
- Create `/auth/register` (optional, or just for testing).

#### [MODIFY] [dependencies.py](file:///home/abok/Desktop/pcd_ws/project/app/api/dependencies.py)
- Add `get_current_user`: Extracts user from JWT and validates they exist in DB.
- Add `check_admin_role`: Dependency that raises 403 if user is not an Admin.

#### [MODIFY] [datasets.py](file:///home/abok/Desktop/pcd_ws/project/app/api/datasets.py)
- Protect `upload_lidar` and `process_lidar` with `Depends(check_admin_role)`.
- Allow `list_datasets` and `download_zone` for all authenticated users.

---

### Frontend (React/Vite)

#### [NEW] [Login.jsx](file:///home/abok/Desktop/pcd_ws/project/frontend/src/components/Login.jsx)
- A simple login page to select a role and obtain a token.

#### [MODIFY] [App.jsx](file:///home/abok/Desktop/pcd_ws/project/frontend/src/App.jsx)
- Wrap the app in an `AuthProvider` or use a simple state to track the logged-in user.
- **Conditional UI**:
    - Hide the "Upload Dataset" button if the user is not an Admin.
    - Disable or hide processing triggers in the dataset list for regular users.
    - Show a "User Profile" badge indicating the current role.

#### [MODIFY] [api.js](file:///home/abok/Desktop/pcd_ws/project/frontend/src/api.js)
- Update Axios instance to automatically include the `Authorization: Bearer <token>` header in all requests.

---

## Verification Plan

### Automated Tests
- Run `pytest` to ensure existing functionality remains intact.
- Add new tests in `tests/test_auth.py`:
    - Verify Admin can upload.
    - Verify Regular User receives `403 Forbidden` on upload.

### Manual Verification
1. Log in as **Admin**:
    - Confirm "Upload" button is visible.
    - Successfully upload and process a file.
2. Log in as **Regular User**:
    - Confirm "Upload" button is hidden.
    - Confirm map selection and download still work.
    - Try to hit the `/lidar/upload` endpoint manually using `curl` and verify it fails.
