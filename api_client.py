from bybit_p2p import P2P

def get_api(config):
    return P2P(
        testnet=config["bybit"]["testnet"],
        api_key=config["bybit"]["api_key"],
        api_secret=config["bybit"]["api_secret"],
        recv_window=20000
    )

