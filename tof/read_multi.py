from felix.nodes.tof_cluster import TOFCluster
import asyncio
from felix.signals import sig_tof

cluster = TOFCluster(debug=True)

def on_tof(sender, payload):
    print("GOT", payload)

sig_tof.connect(on_tof)

async def main():
    await cluster.spin(5)

if __name__ == "__main__":
    asyncio.run(main())

    