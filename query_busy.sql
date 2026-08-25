-- Loginy osób zajętych przez zamówienia typu 7 in_progress.
SELECT DISTINCT COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)) AS UserName
FROM [SerwisKop_Magazyn].[Document].[Documents] DD
LEFT JOIN Core.Users CU ON CU.Id = TRY_CONVERT(int, DD.ModifiedBy)
WHERE DD.DocumentType = 7
  AND DD.SubType = 50
  AND DD.DocumentStatusText = 'in_progress'
  AND DD.DateCreatedUtc >= '2026-08-01';
