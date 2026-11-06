"""Order persistence, lifecycle, and assignment service for Phase 5."""

import sqlite3
import threading
import uuid
from datetime import UTC, datetime

from app.models.order import (
    PERMITTED_TRANSITIONS,
    TRANSITION_ROLES,
    AssignPartnerRequest,
    OrderAssignment,
    OrderEvent,
    OrderRecord,
    OrderSnapshot,
    OrderSummary,
    TransitionOrderRequest,
)
from app.models.pricing import QuoteResponse
from app.services.applicant_service import (
    APPLICANT_DATABASE_PATH,
    _DATABASE_LOCK,
    get_applicant,
)

_ORDER_LOCK = threading.RLock()

_SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS orders (
        order_id      TEXT PRIMARY KEY,
        applicant_id  TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'ORDER_PLACED',
        snapshot_json TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        FOREIGN KEY (applicant_id) REFERENCES applicants(applicant_id)
    )""",
    """CREATE TABLE IF NOT EXISTS order_events (
        event_id        TEXT PRIMARY KEY,
        order_id        TEXT NOT NULL,
        event_type      TEXT NOT NULL,
        from_status     TEXT,
        to_status       TEXT NOT NULL,
        actor_username  TEXT NOT NULL,
        actor_role      TEXT NOT NULL,
        reason          TEXT,
        detail          TEXT,
        created_at      TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )""",
    """CREATE TABLE IF NOT EXISTS order_assignments (
        assignment_id        TEXT PRIMARY KEY,
        order_id             TEXT NOT NULL,
        partner_username     TEXT NOT NULL,
        assigned_by_username TEXT NOT NULL,
        assigned_at          TEXT NOT NULL,
        reason               TEXT,
        superseded_at        TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_orders_applicant ON orders(applicant_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_assignments_order ON order_assignments(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_assignments_partner ON order_assignments(partner_username)",
]


class OrderNotFoundError(ValueError):
    pass


class OrderStateError(ValueError):
    pass


class OrderAuthorizationError(PermissionError):
    pass


class DuplicateOrderError(ValueError):
    pass


class InvalidQuoteError(ValueError):
    pass


def _connect() -> sqlite3.Connection:
    APPLICANT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(APPLICANT_DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in _SCHEMA_SQL:
        conn.execute(stmt)
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _fetch_events(conn: sqlite3.Connection, order_id: str) -> list[OrderEvent]:
    rows = conn.execute(
        "SELECT * FROM order_events WHERE order_id = ? ORDER BY created_at ASC",
        (order_id,),
    ).fetchall()
    return [OrderEvent(**dict(r)) for r in rows]


def _fetch_assignment(conn: sqlite3.Connection, order_id: str) -> OrderAssignment | None:
    row = conn.execute(
        """SELECT * FROM order_assignments
           WHERE order_id = ? AND superseded_at IS NULL
           ORDER BY assigned_at DESC LIMIT 1""",
        (order_id,),
    ).fetchone()
    return OrderAssignment(**dict(row)) if row else None


def _build_record(row: sqlite3.Row, conn: sqlite3.Connection) -> OrderRecord:
    return OrderRecord(
        order_id=row["order_id"],
        applicant_id=row["applicant_id"],
        status=row["status"],
        snapshot=OrderSnapshot.model_validate_json(row["snapshot_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        current_assignment=_fetch_assignment(conn, row["order_id"]),
        events=_fetch_events(conn, row["order_id"]),
    )


def _append_event(
    conn: sqlite3.Connection,
    order_id: str,
    event_type: str,
    from_status: str | None,
    to_status: str,
    actor_username: str,
    actor_role: str,
    reason: str | None = None,
    detail: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO order_events
           (event_id, order_id, event_type, from_status, to_status,
            actor_username, actor_role, reason, detail, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (_new_id(), order_id, event_type, from_status, to_status,
         actor_username, actor_role, reason, detail, _now()),
    )


def place_order(
    applicant_id: str,
    actor_username: str,
    actor_role: str,
) -> OrderRecord:
    if actor_role != "CUSTOMER":
        raise OrderAuthorizationError("Only customers may place orders.")
    applicant = get_applicant(applicant_id)
    if applicant.latest_quote is None:
        raise InvalidQuoteError("No quote is available. Generate a quote first.")
    quote: QuoteResponse = applicant.latest_quote
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        existing = conn.execute(
            "SELECT order_id FROM orders WHERE applicant_id = ? AND status != 'CANCELLED'",
            (applicant_id,),
        ).fetchone()
        if existing:
            raise DuplicateOrderError(
                "An active order already exists for this applicant."
            )
        quote_row = conn.execute(
            """SELECT quote_id, created_at FROM quote_previews
               WHERE applicant_id = ?
               ORDER BY created_at DESC, quote_id DESC LIMIT 1""",
            (applicant_id,),
        ).fetchone()
        if quote_row is None:
            raise InvalidQuoteError("No persisted quote found for this applicant.")
        snapshot = OrderSnapshot(
            quote_id=quote_row["quote_id"],
            line_items=quote.line_items,
            total_monthly_min_inr=quote.total_monthly_min_inr,
            total_monthly_max_inr=quote.total_monthly_max_inr,
            total_one_time_setup_inr=quote.total_one_time_setup_inr,
            quote_created_at=quote_row["created_at"],
        )
        order_id = _new_id()
        now = _now()
        conn.execute(
            """INSERT INTO orders
               (order_id, applicant_id, status, snapshot_json, created_at, updated_at)
               VALUES (?, ?, 'ORDER_PLACED', ?, ?, ?)""",
            (order_id, applicant_id, snapshot.model_dump_json(), now, now),
        )
        _append_event(conn, order_id, "ORDER_PLACED", None, "ORDER_PLACED",
                      actor_username, actor_role, detail="Order placed by customer.")
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return _build_record(row, conn)


def get_order(order_id: str) -> OrderRecord:
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise OrderNotFoundError(f"Order '{order_id}' was not found.")
        return _build_record(row, conn)


def list_orders_for_applicant(applicant_id: str) -> list[OrderSummary]:
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE applicant_id = ? ORDER BY created_at DESC",
            (applicant_id,),
        ).fetchall()
        result = []
        for row in rows:
            a = _fetch_assignment(conn, row["order_id"])
            snap = OrderSnapshot.model_validate_json(row["snapshot_json"])
            result.append(OrderSummary(
                order_id=row["order_id"],
                applicant_id=row["applicant_id"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                partner_username=a.partner_username if a else None,
                total_monthly_min_inr=snap.total_monthly_min_inr,
                total_monthly_max_inr=snap.total_monthly_max_inr,
                total_one_time_setup_inr=snap.total_one_time_setup_inr,
            ))
        return result


def list_all_orders(
    status_filter: str | None = None,
    search: str | None = None,
) -> list[OrderSummary]:
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            if search and search.lower() not in (row["order_id"] + row["applicant_id"]).lower():
                continue
            a = _fetch_assignment(conn, row["order_id"])
            snap = OrderSnapshot.model_validate_json(row["snapshot_json"])
            result.append(OrderSummary(
                order_id=row["order_id"],
                applicant_id=row["applicant_id"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                partner_username=a.partner_username if a else None,
                total_monthly_min_inr=snap.total_monthly_min_inr,
                total_monthly_max_inr=snap.total_monthly_max_inr,
                total_one_time_setup_inr=snap.total_one_time_setup_inr,
            ))
        return result


def list_orders_for_partner(partner_username: str) -> list[OrderSummary]:
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT o.* FROM orders o
               INNER JOIN order_assignments a
                 ON o.order_id = a.order_id
                 AND a.partner_username = ?
                 AND a.superseded_at IS NULL
               ORDER BY o.created_at DESC""",
            (partner_username,),
        ).fetchall()
        result = []
        for row in rows:
            snap = OrderSnapshot.model_validate_json(row["snapshot_json"])
            result.append(OrderSummary(
                order_id=row["order_id"],
                applicant_id=row["applicant_id"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                partner_username=partner_username,
                total_monthly_min_inr=snap.total_monthly_min_inr,
                total_monthly_max_inr=snap.total_monthly_max_inr,
                total_one_time_setup_inr=snap.total_one_time_setup_inr,
            ))
        return result


def transition_order(
    order_id: str,
    request: TransitionOrderRequest,
    actor_username: str,
    actor_role: str,
) -> OrderRecord:
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise OrderNotFoundError(f"Order '{order_id}' was not found.")
        current = row["status"]
        to = request.to_status
        if to not in PERMITTED_TRANSITIONS.get(current, set()):
            raise OrderStateError(
                f"Transition from '{current}' to '{to}' is not permitted."
            )
        allowed_roles = TRANSITION_ROLES.get((current, to), set())
        if actor_role not in allowed_roles:
            raise OrderAuthorizationError(
                f"Role '{actor_role}' cannot perform this transition."
            )
        if actor_role == "PARTNER":
            assignment = _fetch_assignment(conn, order_id)
            if assignment is None or assignment.partner_username != actor_username:
                raise OrderAuthorizationError(
                    "You are not the assigned partner for this order."
                )
        # CUSTOMER transitions are only reachable via the customer cancel API,
        # which verifies applicant ownership before calling this service.
        now = _now()
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (to, now, order_id),
        )
        _append_event(conn, order_id, "STATUS_TRANSITION", current, to,
                      actor_username, actor_role,
                      reason=request.reason, detail=request.detail)
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return _build_record(row, conn)





def assign_partner(
    order_id: str,
    request: AssignPartnerRequest,
    actor_username: str,
    actor_role: str,
    all_accounts: dict,
) -> OrderRecord:
    if actor_role != "OPERATIONS":
        raise OrderAuthorizationError("Only operations users may assign partners.")
    partner_account = all_accounts.get(request.partner_username)
    if partner_account is None or partner_account.role != "PARTNER":
        raise OrderAuthorizationError(
            f"'{request.partner_username}' is not a configured PARTNER account."
        )
    with _ORDER_LOCK, _DATABASE_LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise OrderNotFoundError(f"Order '{order_id}' was not found.")
        if row["status"] in ("CANCELLED", "ACTIVATED"):
            raise OrderStateError(
                f"Cannot assign a partner to an order in '{row['status']}' status."
            )
        now = _now()
        conn.execute(
            "UPDATE order_assignments SET superseded_at = ? WHERE order_id = ? AND superseded_at IS NULL",
            (now, order_id),
        )
        conn.execute(
            """INSERT INTO order_assignments
               (assignment_id, order_id, partner_username, assigned_by_username,
                assigned_at, reason, superseded_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL)""",
            (_new_id(), order_id, request.partner_username, actor_username, now, request.reason),
        )
        current = row["status"]
        if current == "ORDER_PLACED":
            conn.execute(
                "UPDATE orders SET status = 'ASSIGNED', updated_at = ? WHERE order_id = ?",
                (now, order_id),
            )
            _append_event(conn, order_id, "STATUS_TRANSITION", "ORDER_PLACED", "ASSIGNED",
                          actor_username, actor_role, reason=request.reason,
                          detail=f"Assigned to partner: {request.partner_username}")
        else:
            conn.execute(
                "UPDATE orders SET updated_at = ? WHERE order_id = ?", (now, order_id)
            )
            _append_event(conn, order_id, "PARTNER_REASSIGNED", current, current,
                          actor_username, actor_role, reason=request.reason,
                          detail=f"Reassigned to partner: {request.partner_username}")
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return _build_record(row, conn)
