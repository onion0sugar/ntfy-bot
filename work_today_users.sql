-- Users from users.txt who modified at least one document today.
-- {usernames} is replaced with parameter placeholders by the application.
SELECT CU.UserName,
MAX(ZGU.ZoneGroupId) AS MaxZoneGroupId
  FROM [SerwisKop_Magazyn].[Package].[PackagePositions] DD WITH (NOLOCK)
  INNER JOIN Core.Users CU WITH (NOLOCK) ON DD.CreatedBy = CU.Id
  LEFT JOIN [SerwisKop_Magazyn].[Zone].[ZoneGroupUsers] ZGU WITH (NOLOCK) ON CU.Id = ZGU.UserId
    WHERE DD.DateModifiedUtc >= CAST(GETDATE() AS DATE)
  AND CU.UserName IN ({usernames})
GROUP BY CU.UserName;
