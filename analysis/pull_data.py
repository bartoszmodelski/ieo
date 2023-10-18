import databento

client = databento.Historical("db-LjMNngNxbdS9BnhrhGcuBUewcSynJ")
data = client.timeseries.get_range(
    dataset="DBEQ.BASIC",
    #symbols="USO",
    symbols="IEO",
    #symbols="SPY",
    start="2023-03-28T00:01",
    end="2023-10-01T23:59",
    schema="mbo"
    #schema="trades"
)

data.to_file("eio-mbo-5m")


#data.replay(print)

