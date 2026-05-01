using Microsoft.Data.Sqlite;

var builder = WebApplication.CreateBuilder(args);

// Allow the app to serve our HTML/JS files
builder.Services.AddEndpointsApiExplorer();
var app = builder.Build();

app.UseDefaultFiles(); // Looks for index.html
app.UseStaticFiles();  // Serves files from the wwwroot folder

string dbPath = "Data Source=/data/macbooks.db";

// Endpoint 1: Get Products with Filters (Updated for Lifetime & Condition)
app.MapGet("/api/products", (
    string? search, 
    decimal? minPrice, 
    decimal? maxPrice,
    int? minRam,
    int? exactRam,
    int? minStorage,
    int? exactStorage,
    string? type,
    string? status,     // "active", "inactive", or "all"
    string? condition,  // "sealed", "unsealed", or "all"
    string? category    // "Laptop", "Tablet", or null/all
    ) =>
{
    var products = new List<object>();
    using var connection = new SqliteConnection(dbPath);
    connection.Open();

    // Added 1=1 as a dummy true statement so we can easily append "AND" clauses
    // Added p.active, p.sealed, and p.last_seen to the SELECT clause
    var query = @"
        SELECT p.id_product, m.title, p.current_price, p.platform, p.link, 
               m.ram, m.storage, m.cpu, p.active, p.sealed, p.last_seen,
               m.category, m.connectivity
        FROM product p 
        JOIN model m ON p.id_model = m.id_model 
        WHERE 1=1 "; 

    // Status Filter
    if (status == "active") query += " AND p.active = 1 ";
    else if (status == "inactive") query += " AND p.active = 0 ";

    // Condition Filter
    if (condition == "sealed") query += " AND p.sealed = 1 ";
    else if (condition == "unsealed") query += " AND p.sealed = 0 ";

    if (!string.IsNullOrEmpty(category)) query += " AND m.category = @category ";
    if (!string.IsNullOrEmpty(search)) query += " AND m.title LIKE @search ";
    if (minPrice.HasValue) query += " AND p.current_price >= @minPrice ";
    if (maxPrice.HasValue) query += " AND p.current_price <= @maxPrice ";
    if (minRam.HasValue) query += " AND m.ram >= @minRam ";
    if (exactRam.HasValue) query += " AND m.ram = @exactRam ";
    if (minStorage.HasValue) query += " AND m.storage >= @minStorage ";
    if (exactStorage.HasValue) query += " AND m.storage = @exactStorage ";
    if (!string.IsNullOrEmpty(type)) query += " AND m.type = @type ";
    
    query += " ORDER BY p.current_price ASC";

    using var command = new SqliteCommand(query, connection);
    
    if (!string.IsNullOrEmpty(category)) command.Parameters.AddWithValue("@category", category);
    if (!string.IsNullOrEmpty(search)) command.Parameters.AddWithValue("@search", $"%{search}%");
    if (minPrice.HasValue) command.Parameters.AddWithValue("@minPrice", minPrice.Value);
    if (maxPrice.HasValue) command.Parameters.AddWithValue("@maxPrice", maxPrice.Value);
    if (minRam.HasValue) command.Parameters.AddWithValue("@minRam", minRam.Value);
    if (exactRam.HasValue) command.Parameters.AddWithValue("@exactRam", exactRam.Value);
    if (minStorage.HasValue) command.Parameters.AddWithValue("@minStorage", minStorage.Value);
    if (exactStorage.HasValue) command.Parameters.AddWithValue("@exactStorage", exactStorage.Value);
    if (!string.IsNullOrEmpty(type)) command.Parameters.AddWithValue("@type", type);

    using var reader = command.ExecuteReader();
    while (reader.Read())
    {
        string categoryVal = reader.GetString(11);
        string connectivityVal = reader.GetString(12);
        string specs;
        if (categoryVal == "Tablet") {
             specs = $"{reader.GetString(7)} | {connectivityVal} | {reader.GetInt32(6)}GB";
        } else {
             specs = $"{reader.GetString(7)} | {reader.GetInt32(5)}GB RAM | {reader.GetInt32(6)}GB SSD";
        }

        products.Add(new {
            Id = reader.GetInt32(0),
            Title = reader.GetString(1),
            Price = reader.IsDBNull(2) ? 0 : reader.GetDecimal(2),
            Platform = reader.GetString(3),
            Link = reader.GetString(4),
            Specs = specs,
            Active = reader.GetInt32(8) == 1,
            Sealed = reader.GetInt32(9) == 1,
            LastSeen = reader.GetString(10),
            Category = categoryVal,
            Connectivity = connectivityVal
        });
    }
    return Results.Ok(products);
});

// Endpoint 2: Get Price History (Smart branching for Sealed vs Unsealed)
app.MapGet("/api/products/{id}/history", (int id) =>
{
    int idModel = 0;
    int isSealed = 1;
    using var connection = new SqliteConnection(dbPath);
    connection.Open();
    
    // 1. Check if the requested product is sealed or unsealed, and get its model ID
    using (var cmd = new SqliteCommand("SELECT id_model, sealed FROM product WHERE id_product = @id", connection))
    {
        cmd.Parameters.AddWithValue("@id", id);
        using var r = cmd.ExecuteReader();
        if (r.Read()) {
            idModel = r.GetInt32(0);
            isSealed = r.GetInt32(1);
        }
    }

    var historyList = new List<object>();
    string query;
    
    if (isSealed == 1) 
    {
        // SEALED: Get the exact history of this specific product listing
        query = @"
            SELECT offer_price, recorded_at 
            FROM price_history 
            WHERE id_product = @id 
            ORDER BY recorded_at ASC";
            
        using var command = new SqliteCommand(query, connection);
        command.Parameters.AddWithValue("@id", id);
        using var reader = command.ExecuteReader();
        while (reader.Read()) {
            historyList.Add(new { Price = reader.GetDecimal(0), Date = reader.GetString(1).Replace(" ", "T") });
        }
    } 
    else 
    {
        // UNSEALED: Get the LOWEST available price on each day across ALL unsealed items of this model
        query = @"
            SELECT MIN(ph.offer_price), date(ph.recorded_at) as day
            FROM price_history ph
            JOIN product p ON ph.id_product = p.id_product
            WHERE p.id_model = @idModel AND p.sealed = 0
            GROUP BY day
            ORDER BY day ASC";
            
        using var command = new SqliteCommand(query, connection);
        command.Parameters.AddWithValue("@idModel", idModel);
        using var reader = command.ExecuteReader();
        while (reader.Read()) {
            // date() returns YYYY-MM-DD format
            historyList.Add(new { Price = reader.GetDecimal(0), Date = reader.GetString(1) }); 
        }
    }

    // Return the data AND the status so the frontend knows how to draw the chart
    return Results.Ok(new {
        IsSealed = isSealed == 1,
        History = historyList
    });
});

app.Run();