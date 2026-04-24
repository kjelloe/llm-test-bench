using MicroAzureSas;

namespace MicroAzureSasTests;

public class SasHelperTests
{
    // Azurite / dev-storage well-known credentials — no real Azure account needed.
    private const string DevConnectionString =
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;" +
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;" +
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;";

    [Fact]
    public void GenerateSasUri_ReturnsNonNullUri()
    {
        var uri = SasHelper.GenerateSasUri(DevConnectionString, "mycontainer", "myfile.txt");
        Assert.NotNull(uri);
    }

    [Fact]
    public void GenerateSasUri_ExpiresOnIsAtLeast50MinutesInFuture()
    {
        var uri = SasHelper.GenerateSasUri(DevConnectionString, "mycontainer", "myfile.txt");
        var se = ParseSeParam(uri);
        Assert.True(
            se > DateTimeOffset.UtcNow.AddMinutes(50),
            $"Expected ExpiresOn > now+50min, got {se:O}"
        );
    }

    [Fact]
    public void GenerateSasUri_ExpiresOnIsNoMoreThan70MinutesInFuture()
    {
        var uri = SasHelper.GenerateSasUri(DevConnectionString, "mycontainer", "myfile.txt");
        var se = ParseSeParam(uri);
        Assert.True(
            se < DateTimeOffset.UtcNow.AddMinutes(70),
            $"Expected ExpiresOn < now+70min, got {se:O}"
        );
    }

    private static DateTimeOffset ParseSeParam(Uri uri)
    {
        var query = uri.Query.TrimStart('?');
        foreach (var part in query.Split('&'))
        {
            var kv = part.Split('=', 2);
            if (kv.Length == 2 && kv[0] == "se")
                return DateTimeOffset.Parse(Uri.UnescapeDataString(kv[1]));
        }
        throw new InvalidOperationException("SAS URI is missing the 'se' (expiry) query parameter");
    }
}
