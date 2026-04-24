using Azure.Storage.Blobs;
using Azure.Storage.Sas;

namespace MicroAzureSas;

public static class SasHelper
{
    public static Uri GenerateSasUri(string connectionString, string containerName, string blobName)
    {
        var blobClient = new BlobServiceClient(connectionString)
            .GetBlobContainerClient(containerName)
            .GetBlobClient(blobName);

        var builder = new BlobSasBuilder
        {
            BlobContainerName = containerName,
            BlobName = blobName,
            Resource = "b",
            ExpiresOn = DateTimeOffset.UtcNow.AddMinutes(-10), // BUG: expiry is in the past
        };
        builder.SetPermissions(BlobSasPermissions.Read);

        return blobClient.GenerateSasUri(builder);
    }
}
