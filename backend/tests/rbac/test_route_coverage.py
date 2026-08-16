"""Phase 12: automated RBAC route-coverage check.

Enumerates every registered API route and asserts each one is either
explicitly allow-listed below as intentionally public, or has an
authentication/authorization dependency (`app.rbac.dependencies.
require_permission(...)`, or - for the handful of identity-only endpoints
that intentionally require *authentication* without a specific permission -
`app.auth.dependencies.get_current_user`/`get_current_active_user`)
somewhere in its resolved dependency tree.

This turns a one-time manual RBAC review into a standing regression test:
any future route added without an auth/permission dependency fails this
test immediately, the same day it's added, rather than depending on
someone remembering to check by hand. See SECURITY.md for the full RBAC
coverage summary this test enforces.
"""

from fastapi.routing import APIRoute

from app.main import app

# Every route NOT listed here must carry an auth/permission dependency -
# see test_every_route_is_public_or_protected. Each entry is deliberately
# and individually justified, not a blanket exemption:
#   - GET /health: liveness/readiness probe (Docker/CI/monitoring need this
#     reachable with no credential - see app/api/health.py).
#   - POST /auth/register, POST /auth/login: identity bootstrap - there is
#     no token to present yet. Registration always grants VIEWER only (see
#     app/auth/service.py); nothing sensitive is exposed by either route.
_PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
}

# Substrings of a dependency callable's __qualname__ that indicate the
# route requires, at minimum, a valid authenticated user -
# require_permission(...) returns a closure that further calls
# get_current_active_user itself, so matching on any one of these anywhere
# in the tree is sufficient.
_AUTH_MARKERS = ("require_permission", "get_current_user", "get_current_active_user")


def _iter_api_routes() -> list[APIRoute]:
    """Flatten FastAPI's route tree into real APIRoute objects.

    FastAPI wraps included routers in an internal `_IncludedRouter` whose
    actual routes live on `.original_router.routes` - `app.routes` is not
    already a flat list of APIRoute. `/docs`, `/redoc`, `/openapi.json` are
    plain Starlette `Route`s (not APIRoute) and are excluded by the
    isinstance check below; they carry no application data and don't need
    an allow-list entry.
    """

    def walk(routes: list) -> list[APIRoute]:
        collected: list[APIRoute] = []
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                collected.extend(walk(route.original_router.routes))
            elif isinstance(route, APIRoute):
                collected.append(route)
        return collected

    return walk(app.routes)


def _is_protected(route: APIRoute) -> bool:
    stack = list(route.dependant.dependencies)
    seen: set[int] = set()
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        name = getattr(call, "__qualname__", "") or getattr(call, "__name__", "")
        if any(marker in name for marker in _AUTH_MARKERS):
            return True
        stack.extend(dep.dependencies)
    return False


def test_every_route_is_public_or_protected() -> None:
    api_routes = _iter_api_routes()
    # A hardcoded floor, not a moving target: catches the whole check
    # silently becoming a no-op if route discovery ever breaks (e.g. a
    # FastAPI upgrade changes internal route wrapping again).
    assert len(api_routes) >= 50, (
        f"expected at least 50 registered API routes, found {len(api_routes)} - "
        "route discovery may be broken, not the app actually shrinking"
    )

    unprotected = sorted(
        (method, route.path)
        for route in api_routes
        for method in route.methods - {"HEAD", "OPTIONS"}
        if (method, route.path) not in _PUBLIC_ROUTES and not _is_protected(route)
    )

    assert not unprotected, (
        "Routes reachable with no auth/permission dependency and not "
        f"explicitly allow-listed as intentionally public in _PUBLIC_ROUTES: {unprotected}"
    )


def test_public_allow_list_has_no_stale_entries() -> None:
    """Catches the allow-list itself going stale (a route renamed/removed
    without updating _PUBLIC_ROUTES), which would otherwise silently widen
    over time instead of narrowing."""
    api_routes = _iter_api_routes()
    actual = {
        (method, route.path) for route in api_routes for method in route.methods - {"HEAD", "OPTIONS"}
    }
    stale = _PUBLIC_ROUTES - actual
    assert not stale, f"_PUBLIC_ROUTES lists routes that no longer exist: {stale}"
