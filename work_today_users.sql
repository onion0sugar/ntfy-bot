-- Users from users.txt who modified at least one document today.
-- {usernames} is replaced with parameter placeholders by the application.
SELECT DISTINCT CU.UserName
FROM [SerwisKop_Magazyn].[Document].[Documents] DD
INNER JOIN Core.Users CU ON DD.ModifiedBy = CU.Id
WHERE DD.DateModifiedUtc >= CAST(GETDATE() AS DATE)
  AND CU.UserName IN ({usernames});
