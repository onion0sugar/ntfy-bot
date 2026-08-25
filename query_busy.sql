-- Loginy osób zajętych przez zamówienia typu 7 in_progress.
SELECT DISTINCT COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)) AS UserName
FROM [SerwisKop_Magazyn].[Document].[Documents] DD
LEFT JOIN Core.Users CU ON CU.Id = TRY_CONVERT(int, DD.ModifiedBy)
LEFT JOIN [SerwisKop_Magazyn].[Document].[CustomerOrderDocumentConfigurations] CONF
  ON CONF.Id = DD.CustomerOrderDocumentConfigurationId
LEFT JOIN Package.PackageStats PS ON PS.DocumentId = DD.Id
WHERE DD.DateCreatedUtc >= DATEADD(DAY, -30, GETUTCDATE())
  AND DD.SubType = 50
  AND (DD.DocumentType = 7 AND DD.DocumentStatusText = 'in_progress')
  --OR (DD.DocumentType = 22 AND CONF.CourierId = 13 AND DD.DocumentStatusText != 'end')