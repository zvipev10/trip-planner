const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
(async()=>{
 const b=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});const p=await b.newPage({viewport:{width:390,height:844}});
 await p.goto('http://127.0.0.1:8766/web/');
 await p.evaluate(()=>localStorage.setItem('trip-planner.web.v1',JSON.stringify([{id:'x',title:'Saved day',revision:1,startId:'a',endId:'a',places:[{id:'a',name:'Home',address:'',latitude:32,longitude:35},{id:'b',name:'Visit',address:'',latitude:32.01,longitude:35.01}],plan:{revision:1,order:['b'],distance:300,legs:[100,200],manual:false,stale:false,geometry:[[35,32],[35.01,32.01],[35,32]]}}])));
 await p.reload();await p.getByRole('button',{name:'Saved day',exact:false}).click();
 await p.locator('.result:not(.stale)').waitFor();
 if(await p.locator('.endpoint-editor').getAttribute('open')!==null)throw Error('endpoints expanded by default');
 if(await p.locator('#start-select').inputValue()!=='a'||await p.locator('#end-select').inputValue()!=='a')throw Error('endpoints lost');
 await p.locator('.endpoint-editor summary').click();await p.locator('#end-select').selectOption('b');
 if(await p.locator('.result').count())throw Error('old route survived endpoint change');
 await p.reload();await p.getByRole('button',{name:'Saved day',exact:false}).click();
 if(await p.locator('#end-select').inputValue()!=='b')throw Error('edited endpoint not persisted');
 console.log('PASS saved route restored, endpoint editor collapsed, endpoint edits invalidate route and persist');await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
