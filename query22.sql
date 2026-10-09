WITH PPP_Agg AS (
    SELECT DocumentId,
           COUNT(*) AS IlePozycji
    FROM [SerwisKop_Magazyn].[Package].[PackagePositions] WITH (NOLOCK)
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
       DL.ID AS ReadyTriggerId
FROM [SerwisKop_Magazyn].[Document].[Documents] DD WITH (NOLOCK)
OUTER APPLY (
    SELECT TOP (1) ZGZ.ZoneGroupId
    FROM [SerwisKop_Magazyn].[Document].[DocumentPositions] DP WITH (NOLOCK)
    LEFT JOIN [Stillage].[StillageSpaces] SS WITH (NOLOCK)
           ON DP.FromStillageSpaceId = SS.Id
    LEFT JOIN [SerwisKop_Magazyn].[Zone].[ZoneGroupZones] ZGZ WITH (NOLOCK)
           ON SS.ZoneId = ZGZ.ZoneId
    WHERE DP.DocumentId = DD.Id
    ORDER BY DP.Id
) ZG
OUTER APPLY (
    SELECT TOP 1 DL.id
    FROM Document.DocumentLogs DL WITH (NOLOCK)
    WHERE DL.DocumentId = DD.ZkDocumentId
      AND DL.CreatedBy = 1
      AND DL.Message LIKE '___Znaleziono dokument: %'
    ORDER BY DL.Id DESC
) DL
LEFT JOIN PPP_Agg PA
       ON PA.DocumentId = DD.Id
LEFT JOIN [SerwisKop_Magazyn].[Document].[CustomerOrderDocumentConfigurations] CONF WITH (NOLOCK)
       ON CONF.Id = DD.CustomerOrderDocumentConfigurationId
LEFT JOIN Core.Users CU WITH (NOLOCK)
       ON CU.Id = DD.ModifiedBy
WHERE DD.DateCreatedUtc >= DATEADD(DAY, -30, GETUTCDATE())
  AND DD.SubType = 50
  AND DD.DocumentType IN (7, 22)
  AND DD.DocumentStatusText IN ('new', 'in_progress');