1. Domain Logon (logon.csv - 3,5 Juta Baris)
:
LOAD CSV WITH HEADERS FROM "file:///logon.csv" AS row
WITH row WHERE NOT row.user IS NULL AND NOT row.pc IS NULL
CALL {
    WITH row
    MERGE (p:PC {pc_id: trim(row.pc)})
    WITH row, p
    MATCH (u:User {user_id: trim(row.user)})
    MERGE (u)-[r:LOGGED_ON_TO {id: trim(row.id)}]->(p)
    SET r.timestamp = datetime(row.date), 
        r.activity = trim(row.activity)
} IN TRANSACTIONS OF 10000 ROWS;

2. Domain Device (device.csv):
LOAD CSV WITH HEADERS FROM "file:///device.csv" AS row
WITH row WHERE NOT row.user IS NULL AND NOT row.pc IS NULL
CALL (row) {
    MERGE (p:PC {pc_id: trim(row.pc)})
    WITH row, p
    MATCH (u:User {user_id: trim(row.user)})
    MERGE (u)-[r:CONNECTED_DEVICE {id: trim(row.id)}]->(p)
    SET r.timestamp = datetime(row.date), 
        r.activity = trim(row.activity), 
        r.file_tree = coalesce(trim(row.file_tree), 'Unknown')
} IN TRANSACTIONS OF 10000 ROWS;


LOAD CSV WITH HEADERS FROM "file:///file.csv" AS row
WITH row WHERE NOT row.user IS NULL AND NOT row.filename IS NULL
CALL (row) {
    MERGE (f:File {filename: trim(row.filename)})
    WITH row, f
    MATCH (u:User {user_id: trim(row.user)})
    MERGE (u)-[r:ACCESSED_FILE {id: trim(row.id)}]->(f)
    SET r.timestamp = datetime(row.date), 
        r.activity = trim(row.activity),
        r.to_removable_media = CASE toLower(trim(row.to_removable_media)) WHEN 'true' THEN true WHEN '1' THEN true WHEN 'yes' THEN true ELSE false END
} IN TRANSACTIONS OF 10000 ROWS


LOAD CSV WITH HEADERS FROM "file:///email.csv" AS row
WITH row WHERE NOT row.user IS NULL AND NOT row.to IS NULL
CALL (row) {
    MERGE (e:Email {address: trim(row.to)})
    WITH row, e
    MATCH (u:User {user_id: trim(row.user)})
    MERGE (u)-[r:SENT_EMAIL {id: trim(row.id)}]->(e)
    SET r.timestamp = datetime(row.date),
        r.activity = trim(row.activity),
        r.size = toInteger(row.size),
        r.attachments = coalesce(trim(row.attachments), 'None'),
        r.cc = coalesce(trim(row.cc), ''),
        r.bcc = coalesce(trim(row.bcc), '')
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM "file:///http.csv" AS row
WITH row WHERE NOT row.user IS NULL AND NOT row.url IS NULL
CALL (row) {
    MERGE (w:URL {url: trim(row.url)})
    WITH row, w
    MATCH (u:User {user_id: trim(row.user)})
    MERGE (u)-[r:VISITED_URL {id: trim(row.id)}]->(w)
    SET r.timestamp = datetime(row.date), 
        r.activity = trim(row.activity)
} IN TRANSACTIONS OF 10000 ROWS;


// 1. Integrasi Profil Psikometrik ke Simpul User
LOAD CSV WITH HEADERS FROM "file:///psychometric.csv" AS row
MERGE (u:User {user_id: trim(row.user_id)})
SET u.O = toInteger(trim(row.O)), 
    u.C = toInteger(trim(row.C)), 
    u.E = toInteger(trim(row.E)), 
    u.A = toInteger(trim(row.A)), 
    u.N = toInteger(trim(row.N));



