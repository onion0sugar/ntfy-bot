;WITH PPP_Agg AS (
    SELECT DocumentId,
           COUNT(*) AS IlePozycji
    FROM [SerwisKop_Magazyn].[Package].[PackagePositions]
    GROUP BY DocumentId
)
SELECT DD.Id,
       DD.OriginalNumber,
       DD.DocumentType,
       CONF.CourierId,
       DD.DocumentStatusText,
       COALESCE(CU.UserName, CONVERT(nvarchar(255), DD.ModifiedBy)) AS UserName,
       ISNULL(PA.IlePozycji, 0) AS IlePozycji
FROM [SerwisKop_Magazyn].[Document].[Documents] DD
LEFT JOIN PPP_Agg PA
       ON PA.DocumentId = DD.Id
LEFT JOIN [SerwisKop_Magazyn].[Document].[CustomerOrderDocumentConfigurations] CONF
       ON CONF.Id = DD.CustomerOrderDocumentConfigurationId
LEFT JOIN Core.Users CU
       ON CU.Id = TRY_CONVERT(int, DD.ModifiedBy)
WHERE DD.DateCreatedUtc >= DATEADD(DAY, -30, GETUTCDATE())
  AND DD.SubType = 50
  AND (
        (DD.DocumentType = 22 AND DD.DocumentStatusText IN ('new', 'in_progress') AND ISNULL(PA.IlePozycji, 0) = 0)
     OR (DD.DocumentType = 7 AND DD.DocumentStatusText = 'new')
  );