# Design Notes

Simple architecture focusing on reliability and tractability.

- Generator are simple RPC servers with two threads: one serving traffic and one computing the signal.
- Likewise the trader: one RPC server and one thread for computing the median.
- Strategies perform most of the work. They connect to generators, pull the signal and submit decisions to the trader.

For the most part things work out of the box. Generator and trader have no dependencies and can be spun up on their own. Once generators and trader are in place, strategies can be spin up and resumed independently.

To make the system more reliable:

- Data production timestamps are checked. If the timestamp is too old system enters error state. This requires all components to have time synchronized to the nearest second. Naturally, there's some leeway in the form of retries and reconnections.
- If any part of the system fails, further components do not produce data, thus propagating the error.
- Trader keeps track of registered strategies. If any strategy unexpectedly stops submitting data, trader enters error state. `deregister.py` can be used to manually deregister strategy to resume operation of trader, while crashed strategy is debugged.

All components are tolerant of others failing, in that they just try to reconnect to their dependencies if any disappears. This has two functions:

- Protects against short-term network blips - important if some part of the infrastructure (perhaps signal generation) was no in the same datacenter.
- In case of a real issue (e.g. crash of signal generator), keeps the infrastructure ready to resume operation as soon as the issue is resolved.

Arguably, there are many ways to approach this problem. Perhaps a more principled design (from dist-systems perspective) would be to use a message bus such as Kafka. However, trading systems tend to differ from typical distributed systems in many ways, e.g. they usually run in a more controlled environment than cloud and the cost of certain malfunctions is significantly higher. Thus, I belive that my simpler but more tractable design is better suited.

# Instruction

Start signal generators:

```
sudo python3 generator.py -p 1000
sudo python3 generator.py -p 1001
sudo python3 generator.py -p 1002
```

Start trader:
```
sudo python3 trader.py -p 1010
```

Start strategies:
```
python3 strategy.py --name "X" --trader-port 1010 --signal-ports 1000
python3 strategy.py --name "Y" --trader-port 1010 --signal-ports 1001,1002
```

As minute passes all components act: generator updates signal, trader checks data and computes median, strategies poll for signal and submit decisions. They all do it at once, thus it's normal to observe some retries:
```
INFO:root:registered X
INFO:root:registered Y
INFO:root:X submitted 0.6741543275356752
INFO:root:median: retrying to compute
INFO:root:Y submitted 0.46357797027309633
INFO:root:median: retrying to compute
INFO:root:median: 0.5688661489043858
```

Stopping components should produce error states, which can be resolved by bringing them back. If certain strategy terminates improperly and cannot be resumed, the error state in trader can be removed as follows.
```
python3 deregister.py -n X
```


# Dependencies

See `requirements.txt`.