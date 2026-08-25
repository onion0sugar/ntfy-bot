-- Dokumenty typu 22; CourierId=13 jest kurierem tego programu.
-- ModifiedBy/UserName powinien wskazywać użytkownika przypisanego do dokumentu.
SELECT DD.Id,
       DD.OriginalNumber,
       DD.DocumentType,
       CONF.CourierId,
       DD.DocumentStatusText,
       COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)) AS UserName,
       PS.[PackagedPositionCount]
FROM [SerwisKop_Magazyn].[Document].[Documents] DD
LEFT JOIN [SerwisKop_Magazyn].[Document].[CustomerOrderDocumentConfigurations] CONF
  ON CONF.Id = DD.CustomerOrderDocumentConfigurationId
LEFT JOIN Core.Users CU ON CU.Id = TRY_CONVERT(int, DD.ModifiedBy)
LEFT JOIN [SerwisKop_Magazyn].[Package].[PackageStats] PS ON PS.DocumentId = DD.Id
WHERE DD.DateCreatedUtc >= DATEADD(DAY, -30, GETUTCDATE())
  AND DD.SubType = 50
  AND DD.DocumentType IN (22, 7)
