import argparse,json,time,urllib.request


def post(base, action, body):
    start=time.monotonic()
    request=urllib.request.Request(base.rstrip('/')+'/'+action,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=90) as response: result=json.load(response)
    return result,round((time.monotonic()-start)*1000)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8002');args=parser.parse_args()
    options={'auto':{'shortest':True,'disable_hierarchy_pruning':True,'exclude_unpaved':True,'exclude_ferries':True}}
    points=[{'lat':32.08+i*0.0003,'lon':34.78+(i%4)*0.001,'type':'break'} for i in range(22)]
    report=[]
    for name, locations in [('normal',points[:2]),('round_trip',[points[0],points[4],points[0]]),('22_point_route',points)]:
        result,ms=post(args.base_url,'route',{'locations':locations,'costing':'auto','costing_options':options,'shape_format':'geojson'})
        assert result['trip']['status']==0 and len(result['trip']['legs'])==len(locations)-1
        report.append({'case':name,'elapsedMs':ms,'kilometers':result['trip']['summary']['length']})
    result,ms=post(args.base_url,'sources_to_targets',{'sources':points,'targets':points,'costing':'auto','costing_options':options})
    matrix=result['sources_to_targets'];assert len(matrix)==22 and all(len(row)==22 for row in matrix)
    assert all(matrix[i][i]['distance']==0 for i in range(22))
    report.append({'case':'22x22_matrix','elapsedMs':ms,'elements':484})
    # Verify the API alias and native engine reject over-limit input.
    try:post(args.base_url,'route',{'locations':points+[points[0]],'costing':'auto'})
    except urllib.error.HTTPError as error:assert error.code==400
    else:raise AssertionError('Over-limit route accepted')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
