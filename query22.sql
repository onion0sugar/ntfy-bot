WITH PPP_Agg AS (
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
       ISNULL(PA.IlePozycji, 0) AS IlePozycji,
       ZG.ZoneGroupId,
       ED.ExternalDocumentId
FROM [SerwisKop_Magazyn].[Document].[Documents] DD
OUTER APPLY (
    SELECT TOP (1) ZGZ.ZoneGroupId
    FROM [SerwisKop_Magazyn].[Document].[DocumentPositions] DP
    LEFT JOIN [Stillage].[StillageSpaces] SS
           ON DP.FromStillageSpaceId = SS.Id
    LEFT JOIN [SerwisKop_Magazyn].[Zone].[ZoneGroupZones] ZGZ
           ON SS.ZoneId = ZGZ.ZoneId
    WHERE DP.DocumentId = DD.Id
    ORDER BY DP.Id
) ZG
OUTER APPLY (
    SELECT TOP 1 *
    FROM Document.DocumentExternalDocuments ED
    WHERE ED.DocumentId = DD.Id
    ORDER BY ED.DocumentId DESC
) ED
LEFT JOIN PPP_Agg PA
       ON PA.DocumentId = DD.Id
LEFT JOIN [SerwisKop_Magazyn].[Document].[CustomerOrderDocumentConfigurations] CONF
       ON CONF.Id = DD.CustomerOrderDocumentConfigurationId
LEFT JOIN Core.Users CU
       ON CU.Id = DD.ModifiedBy
WHERE DD.DateCreatedUtc >= DATEADD(DAY, -30, GETUTCDATE())
  AND DD.SubType = 50
  AND DD.DocumentType IN (7, 22)
  AND DD.DocumentStatusText IN ('new', 'in_progress');

