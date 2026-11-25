import { useCallback, useEffect, useState } from "react";
import { Shield, ShieldOff, RotateCcw, Search } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { listUsers, updateUser, revokeUserSessions } from "../services";

const PAGE_SIZE = 20;

function RoleBadge({ user }) {
  if (user.is_admin) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-signal/15 px-3 py-1 text-xs font-black text-signal">
        Admin
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-3 py-1 text-xs font-black text-slate-300">
      User
    </span>
  );
}

function StatusBadge({ user }) {
  if (!user.is_active) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-danger/15 px-3 py-1 text-xs font-black text-danger">
        Disabled
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-leaf/15 px-3 py-1 text-xs font-black text-leaf">
      Active
    </span>
  );
}

export default function Admin() {
  const { user: me } = useAuth();

  const [search, setSearch] = useState("");
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(
    async (searchValue, offsetValue) => {
      setLoading(true);
      setError("");

      try {
        const response = await listUsers({
          search: searchValue,
          limit: PAGE_SIZE,
          offset: offsetValue,
        });

        setUsers(response.users || []);
        setTotal(response.total || 0);
      } catch (err) {
        setError(err.message || "Couldn't load users.");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    load(search, offset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  function handleSearchSubmit(event) {
    event.preventDefault();
    setOffset(0);
    load(search, 0);
  }

  async function toggleAdmin(target) {
    setBusyId(target.id);
    setError("");
    setNotice("");

    try {
      const response = await updateUser(target.id, {
        is_admin: !target.is_admin,
      });

      setUsers(current =>
        current.map(u => (u.id === target.id ? response.user : u))
      );
    } catch (err) {
      setError(err.message || "Couldn't update that user.");
    } finally {
      setBusyId(null);
    }
  }

  async function toggleActive(target) {
    setBusyId(target.id);
    setError("");
    setNotice("");

    try {
      const response = await updateUser(target.id, {
        is_active: !target.is_active,
      });

      setUsers(current =>
        current.map(u => (u.id === target.id ? response.user : u))
      );
    } catch (err) {
      setError(err.message || "Couldn't update that user.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRevoke(target) {
    setBusyId(target.id);
    setError("");
    setNotice("");

    try {
      await revokeUserSessions(target.id);
      setNotice(`Signed ${target.username || target.email} out everywhere.`);
    } catch (err) {
      setError(err.message || "Couldn't revoke that user's sessions.");
    } finally {
      setBusyId(null);
    }
  }

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black">Admin</h1>
        <p className="mt-1 text-sm text-slate-400">
          Manage accounts: promote or demote admins, enable or disable
          users, and sign a user out of every device.
        </p>
      </div>

      <form onSubmit={handleSearchSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Search
            size={18}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, username, or email"
            className="w-full rounded-2xl pl-10"
          />
        </div>
        <button
          type="submit"
          className="min-h-11 rounded-2xl bg-signal px-5 text-sm font-black text-ink"
        >
          Search
        </button>
      </form>

      {error && (
        <div className="rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
          {error}
        </div>
      )}

      {notice && (
        <div className="rounded-2xl border border-leaf/30 bg-leaf/10 p-4 text-sm text-leaf">
          {notice}
        </div>
      )}

      <div className="overflow-hidden rounded-[24px] border border-white/10 bg-pitch">
        {loading ? (
          <p className="p-6 text-sm text-slate-400">Loading users...</p>
        ) : users.length === 0 ? (
          <p className="p-6 text-sm text-slate-400">No users found.</p>
        ) : (
          <div className="divide-y divide-white/5">
            {users.map(u => {
              const isSelf = me && u.id === me.id;
              const busy = busyId === u.id;

              return (
                <div
                  key={u.id}
                  className="flex flex-wrap items-center justify-between gap-3 p-4"
                >
                  <div className="min-w-0">
                    <p className="truncate font-black">
                      {u.first_name} {u.last_name}{" "}
                      <span className="font-normal text-slate-400">
                        @{u.username}
                      </span>
                      {isSelf && (
                        <span className="ml-2 text-xs font-normal text-slate-500">
                          (you)
                        </span>
                      )}
                    </p>
                    <p className="truncate text-sm text-slate-400">
                      {u.email}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <RoleBadge user={u} />
                    <StatusBadge user={u} />
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={busy || isSelf}
                      onClick={() => toggleAdmin(u)}
                      title={
                        isSelf
                          ? "You can't change your own admin status."
                          : u.is_admin
                          ? "Remove admin access"
                          : "Grant admin access"
                      }
                      className="inline-flex min-h-11 items-center gap-1 rounded-2xl bg-white/10 px-3 text-xs font-black disabled:opacity-40"
                    >
                      {u.is_admin ? <ShieldOff size={14} /> : <Shield size={14} />}
                      {u.is_admin ? "Demote" : "Promote"}
                    </button>

                    <button
                      type="button"
                      disabled={busy || isSelf}
                      onClick={() => toggleActive(u)}
                      title={
                        isSelf
                          ? "You can't disable your own account."
                          : u.is_active
                          ? "Disable this account"
                          : "Re-enable this account"
                      }
                      className={`inline-flex min-h-11 items-center gap-1 rounded-2xl px-3 text-xs font-black disabled:opacity-40 ${
                        u.is_active
                          ? "bg-danger/15 text-danger"
                          : "bg-leaf/15 text-leaf"
                      }`}
                    >
                      {u.is_active ? "Disable" : "Enable"}
                    </button>

                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleRevoke(u)}
                      title="Sign this user out of every device"
                      className="inline-flex min-h-11 items-center gap-1 rounded-2xl bg-white/10 px-3 text-xs font-black disabled:opacity-40"
                    >
                      <RotateCcw size={14} />
                      Revoke
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>
            {Math.min(offset + 1, total)}-{Math.min(offset + PAGE_SIZE, total)}{" "}
            of {total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!canPrev}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="rounded-xl bg-white/10 px-3 py-2 font-black disabled:opacity-40"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={!canNext}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="rounded-xl bg-white/10 px-3 py-2 font-black disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
