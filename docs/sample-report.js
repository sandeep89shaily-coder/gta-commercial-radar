/* GTA Radar research sample. Generates a readable 12-page PDF in-browser.
   No third-party scripts, server requests, or email collection. */
(function(){
"use strict";
const ck=(permit,rev="00")=>"https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search?resource_id=6d0229af-bc54-46de-9c2b-26759b01dd05&filters="+encodeURIComponent(JSON.stringify({PERMIT_NUM:permit,REVISION_NUM:rev}))+"&limit=3";
const projects=[
{city:"Toronto",region:"Toronto",site:"199 Bay Street",scope:"Courtyard skylight replacement and related drainage and structural work.",stage:"Application acceptable",org:"Commerce Court / QuadReal",contact:"QuadReal CONNECT - property management; service@quadrealconnect.com; 1-877-977-2262",fit:"Building envelope, drainage, mechanical and renovation trades",source:ck("26 265599 BLD"),contactSource:"https://www.commercecourt.ca/get-in-touch/",date:"Nov 8, 2026",value:"CAD 1.5M estimated permit value"},
{city:"Toronto",region:"Toronto",site:"4711 Yonge Street",scope:"Interior alterations to elevator lobbies, washrooms and corridors.",stage:"Application acceptable",org:"Menkes Property Management Services",contact:"Elena Muto - property general manager; elena.muto@menkes.com; 416-642-8147",fit:"Renovation, plumbing, access and mechanical",source:ck("26 265943 BLD"),contactSource:"https://www.menkes.com/commercial/projects/4711-yonge-street/contact",date:"Nov 8, 2026",value:"CAD 700K estimated permit value"},
{city:"Toronto",region:"Toronto",site:"250 The East Mall, Unit 125",scope:"Proposed retail fit-up for a Rexall pharmacy.",stage:"Not started in recorded permit",org:"Cloverdale Mall / QuadReal",contact:"Mall management; info@mycloverdale.com; 416-236-1668",fit:"Retail fit-out, security, fire and mechanical systems",source:ck("26 266229 BLD"),contactSource:"https://mycloverdale.com/contact/",date:"Nov 8, 2026",value:"CAD 250K estimated permit value"},
{city:"Mississauga",region:"Peel",site:"2100 Syntex Court",scope:"Active site-plan application for an industrial addition (SP 26/35 W9).",stage:"Active planning application",org:"WBA Architects & Engineers Inc.",contact:"Architectural/engineering applicant named on official source; procurement contact not independently confirmed.",fit:"Industrial construction, mechanical and site systems",source:"https://services6.arcgis.com/hM5ymMLbxIyWTjn2/ArcGIS/rest/services/Site_Plan_Applications/FeatureServer/0/query?where=APP_FILE_NO%3D%27SP%2026%2F35%20W9%27&outFields=*&returnGeometry=false&f=json",date:"Aug 28, 2026",value:"Value not established"},
{city:"Brampton",region:"Peel",site:"5525 Countryside Drive",scope:"Applied industrial F2 building alteration / renovation; site also associated with Prologis development.",stage:"Applied building permit",org:"Prologis - address association",contact:"The site developer is referenced publicly; this specific permit's purchasing contact is unconfirmed.",fit:"Industrial facility systems, renovations and service",source:"https://maps1.brampton.ca/arcgis/rest/services/BuildingPermit/Building_Permits/FeatureServer/0/query?where=PERMITNUMBER%3D%2726-136800-000-00%27&outFields=*&returnGeometry=false&f=json",date:"Aug 24, 2026",value:"Value not established"},
{city:"Burlington",region:"Halton",site:"4495 North Service Road",scope:"Zoning change proposal for two single-storey industrial buildings with accessory office uses.",stage:"Under review in recorded planning source",org:"Dream Summit Industrial",contact:"Developer named on municipal project page; no specific purchasing contact established.",fit:"Industrial construction, mechanical, security and equipment",source:"https://www.burlington.ca/en/news/current-development-projects/4495-North-Service-Road.aspx",date:"Historical planning record",value:"Value not established"},
{city:"Oakville",region:"Halton",site:"2714 Bristol Circle",scope:"Ontario Environmental Registry proposal to replace a dust collector with a scrubber.",stage:"ERO proposal",org:"Pinty's Delicious Foods Inc.",contact:"Official proponent named; supplier procurement channel not identified.",fit:"Air pollution control, scrubbers, industrial equipment and maintenance",source:"https://ero.ontario.ca/notice/026-1152",date:"2026 notice",value:"Value not established"},
{city:"Burlington",region:"Halton",site:"890 Harrington Court",scope:"Ontario Environmental Registry proposal concerning installation of cremation equipment.",stage:"ERO proposal",org:"1000792458 Ontario Ltd.",contact:"Official proponent named; purchasing contact not independently established.",fit:"Specialized process equipment, installation and emissions control",source:"https://ero.ontario.ca/notice/026-1155",date:"2026 notice",value:"Value not established"},
{city:"Waterloo",region:"Waterloo Region",site:"580 Coldstream Drive",scope:"Interior tenant fit-out for a cafe with approximately 30 seats.",stage:"Issued building permit",org:"Tenant not established",contact:"No project-specific public business contact verified in current source record.",fit:"Kitchen ventilation, plumbing, fit-out and fire safety",source:"https://services.arcgis.com/ZpeBVw5o1kjit7LT/arcgis/rest/services/City_of_Waterloo_Building_Permits/FeatureServer/0/query?where=PERMIT_ID%3D410444%20AND%20PERMIT_NUM%3D%272026%20014814%20000%2000%20PMX%27&outFields=*&returnGeometry=false&f=json",date:"Sep 3, 2026",value:"Value not established"},
{city:"St. Catharines",region:"Niagara",site:"295 Fourth Avenue",scope:"Collector record describes commercial exhaust system alterations for East Side Mario's.",stage:"Under inspection in collector record",org:"East Side Mario's - named in record",contact:"Direct project purchaser and original official permit link require verification.",fit:"Restaurant exhaust, ventilation and fire protection",source:"https://www.stcatharines.ca/",date:"May 28, 2026",value:"Value not established; collector-only source"}
];
function download(){
 const ascii=x=>String(x??"").normalize("NFKD").replace(/[\u2018\u2019]/g,"'").replace(/[\u2013\u2014]/g,"-").replace(/[\u201c\u201d]/g,'"').replace(/[^\x20-\x7e]/g," ");
 const esc=x=>ascii(x).replace(/\\/g,"\\\\").replace(/\(/g,"\\(").replace(/\)/g,"\\)");
 const objs=[],add=x=>(objs.push(x),objs.length);
 const catalog=add(""),pages=add("");
 const f1=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
 const f2=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>");
 const pageIds=[];
 function pg(n){
   const ops=[],ann=[];
   function rect(x,y,w,h,c=[.94,.96,.94]){
     ops.push(c.join(" ")+" rg "+[x,y,w,h].join(" ")+" re f");
   }
   function txt(x,y,v,size=10,bold=false,color=[.13,.20,.23]){
     ops.push("BT /"+(bold?"F2":"F1")+" "+size+" Tf "+color.join(" ")+" rg 1 0 0 1 "+x+" "+y+" Tm ("+esc(v)+") Tj ET");
   }
   function para(v,x,y,width=506,size=10,leading=16){
     let current="",line=y;const words=ascii(v).split(/\s+/);
     for(const word of words){
       const candidate=current?current+" "+word:word;
       if(candidate.length*size*.51>width&&current){txt(x,line,current,size);line-=leading;current=word;}
       else current=candidate;
     }
     if(current){txt(x,line,current,size);line-=leading;}
     return line;
   }
   function label(t,y){txt(47,y,t.toUpperCase(),9,true,[.18,.42,.34]);}
   function source(t,url,y){
     txt(47,y,t,9,false,[.14,.34,.58]);
     if(url){
       const i=add("<< /Type /Annot /Subtype /Link /Rect [47 "+(y-4)+" 310 "+(y+12)+"] /Border [0 0 0] /A << /S /URI /URI ("+esc(url)+") >> >>");
       ann.push(i);
     }
   }
   rect(42,752,528,3,[.16,.39,.30]);
   txt(46,769,"GTA COMMERCIAL RADAR  /  SOUTHERN ONTARIO RESEARCH",8,true,[.16,.39,.30]);
   rect(46,45,520,1,[.83,.88,.86]);txt(46,30,"NOVEMBER 2026  /  DATED SOURCE SNAPSHOT",8,false,[.46,.53,.54]);txt(550,30,String(n),8,true,[.46,.53,.54]);
   return {rect,txt,para,label,source,finish(){
     const stream=ops.join("\n")+"\n";
     const content=add("<< /Length "+stream.length+" >>\nstream\n"+stream+"endstream");
     const p=add("<< /Type /Page /Parent "+pages+" 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 "+f1+" 0 R /F2 "+f2+" 0 R >> >> /Contents "+content+" 0 R"+(ann.length?" /Annots ["+ann.map(x=>x+" 0 R").join(" ")+"]":"")+" >>");
     pageIds.push(p);
   }};
 }
 {
   const p=pg(1);p.txt(47,672,"A broader view of",32,true);p.txt(47,628,"what's taking shape.",32,true);
   p.para("Ten researched project signals across seven Southern Ontario municipalities, curated to demonstrate geographic and sector coverage.",47,577,500,12,20);
   p.rect(46,439,520,84,[.92,.96,.92]);p.txt(66,488,"10 PROJECT DOSSIERS",16,true,[.16,.39,.30]);p.txt(322,488,"7 MUNICIPALITIES",16,true,[.16,.39,.30]);
   p.label("REGIONAL SELECTION",397);
   ["Toronto  -  3 projects","Peel (Mississauga and Brampton)  -  2 projects","Halton (Burlington and Oakville)  -  3 projects","Waterloo Region  -  1 project","Niagara  -  1 project"].forEach((v,i)=>p.txt(47,374-i*25,v,11));
   p.label("READING THIS SAMPLE",207);
   p.para("These projects are sourced from saved 2026 research. They are not ten newly announced opportunities. Company and public business contacts are identified only where the source record supports them; open procurement is not assumed.",47,187,506,10,16);
   p.finish();
 }
 projects.forEach((x,i)=>{
   const p=pg(i+2);
   p.label("PROJECT "+String(i+1).padStart(2,"0")+"  /  "+x.city.toUpperCase()+"  /  "+x.region.toUpperCase(),709);
   let y=p.para(x.site,47,674,500,21,28);y-=13;
   p.txt(47,y,"SOURCE STATUS: "+x.stage,10,true);y-=35;
   p.rect(46,y-8,520,59,[.94,.96,.94]);p.txt(57,y+25,"RESEARCH / SOURCE DATE",8,true,[.23,.43,.34]);p.txt(57,y+7,x.date,10);
   p.txt(303,y+25,"CONSTRUCTION VALUE",8,true,[.23,.43,.34]);p.para(x.value,303,y+7,246,9,13);
   y-=54;
   function section(title,body){p.label(title,y);y-=22;y=p.para(body,47,y,505,10,16)-17;}
   section("Recorded activity",x.scope);
   section("Possible relevance",x.fit);
   section("Company context",x.org);
   section("Public contact / qualification route",x.contact);
   p.label("SOURCE REFERENCE",y);y-=23;
   p.source("Open original project / notice source",x.source,y);y-=25;
   if(x.contactSource){p.source("Open company / property contact source",x.contactSource,y);y-=25;}
   y-=10;
   p.para("Evidence note: This is project intelligence, not proof of an unawarded supplier contract or purchasing authority. Refresh the stage before approaching the organization.",47,Math.max(92,y),505,9,13);
   p.finish();
 });
 {
   const p=pg(12);
   p.txt(47,680,"How to read this intelligence",22,true);
   let y=633;
   for(const [title,body] of [
     ["Daily monitoring","Newly detected and changed municipal records can provide earlier awareness; a record first seen by Radar may not be newly announced by the authority."],
     ["Project status","Site-plan applications, issued permits and environmental proposals are different stages. None establishes an open subcontract or supplier bid."],
     ["Contacts","Property managers, applicants, developers and environmental proponents are different roles. Public contact channels are not automatically project buyers."],
     ["Confidence and date","The St. Catharines example is lower-confidence collector evidence and needs exact official-source verification. Every example must be refreshed before commercial use."],
     ["Coverage","These ten records demonstrate seven municipalities across Toronto, Peel, Halton, Waterloo Region and Niagara. Production monitors sources across a broader Southern Ontario footprint, with variable source completeness."]
   ]){
     p.label(title,y);y-=24;y=p.para(body,47,y,507,10,16)-23;
   }
   p.finish();
 }
 objs[catalog-1]="<< /Type /Catalog /Pages "+pages+" 0 R >>";
 objs[pages-1]="<< /Type /Pages /Kids ["+pageIds.map(i=>i+" 0 R").join(" ")+"] /Count "+pageIds.length+" >>";
 let pdf="%PDF-1.4\n",offs=[0];
 objs.forEach((obj,i)=>{offs.push(pdf.length);pdf+=(i+1)+" 0 obj\n"+obj+"\nendobj\n";});
 const xref=pdf.length;pdf+="xref\n0 "+(objs.length+1)+"\n0000000000 65535 f \n";
 offs.slice(1).forEach(i=>pdf+=String(i).padStart(10,"0")+" 00000 n \n");
 pdf+="trailer\n<< /Size "+(objs.length+1)+" /Root "+catalog+" 0 R >>\nstartxref\n"+xref+"\n%%EOF\n";
 const blob=new Blob([pdf],{type:"application/pdf"}),url=URL.createObjectURL(blob);
 const a=document.createElement("a");a.href=url;a.download="GTA_Radar_10_Project_Southern_Ontario_Sample.pdf";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
window.GtaRadarDownloadSamplePdf=download;
})();