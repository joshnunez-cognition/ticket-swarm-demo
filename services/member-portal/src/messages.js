// Secure-message inbox. The table has no index on (member_id, created_at),
// so large inboxes scan the full table.
const INBOX_SQL =
  "SELECT id, subject, created_at FROM messages " +
  "WHERE member_id = ? AND subject LIKE ? ORDER BY created_at DESC LIMIT 50";

function searchInbox(db, memberId, term) {
  return db.query(INBOX_SQL, [memberId, `%${term}%`]);
}

module.exports = { INBOX_SQL, searchInbox };
