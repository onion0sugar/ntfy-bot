-- Suma spakowanych pozycji pracownika dla jednego OriginalNumber.
WITH UserDocumentTotals AS (
    SELECT COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)) AS UserName,
           DD.Id,
           SUM(PS.PackagedPositionCount) AS PackagedPositionCount
    FROM [SerwisKop_Magazyn].[Document].[Documents] DD WITH (NOLOCK)
    LEFT JOIN Core.Users CU WITH (NOLOCK) ON CU.Id = TRY_CONVERT(int, DD.ModifiedBy)
    INNER JOIN [SerwisKop_Magazyn].[Package].[PackageStats] PS WITH (NOLOCK) ON PS.DocumentId = DD.Id
    WHERE DD.DateCreatedUtc >= DATEADD(DAY, -60, GETUTCDATE())
      AND DD.OriginalNumber = ?
      AND DD.SubType = 50
      AND DD.DocumentType = 7
      AND DD.DocumentStatusText = 'end'
      AND COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)) IS NOT NULL
    GROUP BY COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)), DD.Id
),
UserTotals AS (
    SELECT UserName, SUM(PackagedPositionCount) AS PackagedPositionCount
    FROM UserDocumentTotals
    GROUP BY UserName
),
BestUserDocuments AS (
    SELECT UserName,
           Id,
           ROW_NUMBER() OVER (
               PARTITION BY UserName
               ORDER BY PackagedPositionCount DESC, Id
           ) AS DocumentRank
    FROM UserDocumentTotals
)
SELECT U.UserName,
       U.PackagedPositionCount,
       D.Id
FROM UserTotals U
INNER JOIN BestUserDocuments D
        ON D.UserName = U.UserName
       AND D.DocumentRank = 1
ORDER BY U.PackagedPositionCount DESC, U.UserName
