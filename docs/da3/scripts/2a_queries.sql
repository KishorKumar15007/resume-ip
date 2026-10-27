SELECT id, email, left(password_hash, 60) AS password_hash_prefix, role
FROM users
WHERE email LIKE 'da3-salt-%';
