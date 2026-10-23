"""Native-worker deadline and recovery check using prebuilt regional data."""
import argparse
from server import EngineWorker,runtime_config


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);args=parser.parse_args()
    worker=EngineWorker(runtime_config(args.data_dir),timeout=0)
    request={'locations':[{'lat':32.08,'lon':34.78},{'lat':32.09,'lon':34.79}],'costing':'auto','shape_format':'geojson'}
    try:
        status,_=worker.call('route',request)
        assert status==504 and worker.process is None
        worker.timeout=10
        status,result=worker.call('route',request)
        assert status==200 and result['trip']['status']==0
        print('Native deadline termination and next-request recovery passed')
    finally:worker.close()


if __name__=='__main__':main()
