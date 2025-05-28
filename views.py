from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse 
from app.models import *
from app.forms import *
import requests
import json, os
import os
from datetime import datetime, timedelta
import pandas as pd
import locale
import math
from django.utils import timezone
from django.utils.timezone import now
from asgiref.sync import sync_to_async
import numpy as np
from django.core.cache import cache



locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')



# Create your views here.
headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'}
symbols = {'N':'NIFTY', 'F':'FINNIFTY', 'B':'BANKNIFTY'}



def preOpenMarketNify(symbol):
    try:
        url = f'https://www.nseindia.com/api/market-data-pre-open?key={symbols[symbol]}'
        response = requests.get(url, headers=headers, timeout=10)
        json_object = json.loads(response.text)
        return {'price':json_object['niftyPreopenStatus']['lastPrice'], 'change':json_object['niftyPreopenStatus']['change']}
    except:
        return {'price':'19297.4', 'change':'error'}

preMarketNify = preOpenMarketNify('N')
#preMarketBankNify = preOpenMarketNify('B')
preOpenMarket = {'N':preMarketNify}#, 'B':preMarketBankNify}


def optionChain(request, symbol, expiry_date):
    cache_key = f"option_chain_{symbol}_{expiry_date}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, 'app/optionChain.html', cached_data)
    #try:
    url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
    
    response = requests.get(url, headers=headers, timeout=10)
    response_text = response.text
    json_object = json.loads(response_text)
    records = json_object['records']
    filtered = json_object['filtered']
    expiry_dates = records['expiryDates']
    pom = PreMarket.objects.get(id = 1)    # Get last 7 days premarket data
    current_date = timezone.now().date()
    seven_days_ago = current_date - timedelta(days=7)
    premarket_7days = PreMarketData.objects.filter(
        store_date__gte=seven_days_ago,
        store_date__lte=current_date
    ).order_by('-store_date')
    
    # Debug print
    print("PreMarket Debug Info:")
    print(f"Current date: {current_date}")
    print(f"Seven days ago: {seven_days_ago}")
    print(f"Found {premarket_7days.count()} premarket data records")
    print("Latest records:")
    for record in premarket_7days[:3]:
        print(f"Date: {record.store_date}, Open: {record.N_Open}, Close: {record.N_Close}")
    
    NPOM = pom.NPOM
    BNPOM = pom.BNPOM
    FNPOM = pom.FNPOM
    
    underlyingValue = records['underlyingValue']
    #store the above expiry dates in the data list. based on that we get the values of the market.
    data = records['data']
    #to get current market price with rounded strike prices
    current_market_price = round(float(underlyingValue))
    
    
    samp = int(str(current_market_price)[-2:])
    
    
 
    if symbol== 'BANKNIFTY':
        current_market_price = current_market_price-samp+100
    else:        
        if samp>=50:
            current_market_price = current_market_price-samp+100
        else:
            current_market_price = current_market_price-samp+50
    middle = current_market_price

  
    oiList1 = []
    oiList2 = []
    oiList3 = []
    oiList4 = []
    coiList1 = []
    coiList2 = []
    coiList3 = []
    coiList4 = []
    volList1 = [0, 0]
    volList2 = [0, 0]
    
    # <=========================== TO GET STRIKE PRICE 25 TO AND BOTTOM ==========================================>
    if symbol == 'BANKNIFTY':
        d = 100
    else:
        d = 50
    s = set(range(current_market_price-24*d, current_market_price+24*d+1, d))
   
    result = {}
    k = 0

    for i in range(len(data)):
        if data[i]['strikePrice'] in s and data[i]['expiryDate'] == expiry_date:
            if 'CE' in data[i]:
                # CE_OI = (data[i]['CE']['openInterest'])
                CE_OI = data[i]['CE']['openInterest'] if data[i]['CE']['openInterest'] != 0 else 1
                CE_COI = data[i]['CE']['changeinOpenInterest']
                CE_vol = data[i]['CE']['totalTradedVolume'] 
                CE_IV = data[i]['CE']['impliedVolatility']
                CE_LTP = data[i]['CE']['lastPrice']
                CE_chng = round(data[i]['CE']['change'], 4)
                strikePrice1 = data[i]['CE']['strikePrice']
                
            else:
                CE_OI=CE_COI=CE_vol=CE_IV=CE_LTP=CE_chng=strikePrice1=0

            if 'PE' in data[i]:
                PE_COI = data[i]['PE']['changeinOpenInterest']
                # PE_OI = data[i]['PE']['openInterest']
                PE_OI = data[i]['PE']['openInterest'] if data[i]['PE']['openInterest'] != 0 else 1
                PE_vol = data[i]['PE']['totalTradedVolume'] 
                PE_chng = round(data[i]['PE']['change'], 4)
                PE_LTP = data[i]['PE']['lastPrice']
                PE_IV = data[i]['PE']['impliedVolatility']
                strikePrice2 = data[i]['PE']['strikePrice']
            else:
                PE_OI=PE_COI=PE_vol=PE_chng=PE_LTP=PE_IV=strikePrice2=0
            strikePrice = max(strikePrice1, strikePrice2)        
            COI_total = CE_COI+PE_COI
            OI_total = CE_OI+PE_OI
            LTP_TOTAL= CE_LTP+PE_LTP
           # print(OI_total)
            CE_OIP = round((CE_OI/OI_total)*100, 1) if CE_OI !=0 else 0
            CE_volp = round((CE_COI/CE_vol)*100,2) if CE_vol !=0 else 0
            PE_volp = round((PE_COI/PE_vol)*100, 2) if PE_vol !=0 else 0
            PE_OIP = round((PE_OI/OI_total)*100, 1) if OI_total !=0 else 0
            CE_COIP = round((CE_COI/COI_total)*100, 1) if COI_total !=0 else 0
            PE_COIP = round((PE_COI/COI_total)*100, 1) if COI_total !=0 else 0
            # CE_DIR = round((CE_LTP/LTP_TOTAL)*100, 1) if LTP_TOTAL !=0 else 0

        
            if data[i]['strikePrice'] < underlyingValue:
                oiList1.append([CE_OI, data[i]['strikePrice'], k])
                oiList3.append([PE_OI, data[i]['strikePrice'], k])
                coiList1.append([CE_COI, data[i]['strikePrice'], k])
                coiList3.append([PE_COI, data[i]['strikePrice'], k])
            else:
                oiList2.append([CE_OI, data[i]['strikePrice'], k])
                oiList4.append([PE_OI, data[i]['strikePrice'], k])
                coiList2.append([CE_COI, data[i]['strikePrice'], k])
                coiList4.append([PE_COI, data[i]['strikePrice'], k])
               
            volList1 = max(volList1, [CE_vol, k, strikePrice])
            volList2 = max(volList2, [PE_vol, k, strikePrice])

            CE_DIR = round((CE_LTP/LTP_TOTAL)*100,1)

            PE_DIR = round(PE_OI / CE_OI, 2) 
            if PE_DIR >= 2.00 or PE_DIR < 0.1:
                    PE_DIR = 0
         

            # if PE_vol and CE_vol:
            P_DIF = round(PE_vol / (CE_vol if CE_vol != 0 else 1), 2)
            if (P_DIF >= 5.00 or P_DIF < 0.1):
                P_DIF=0         
                           

            result[strikePrice] = {'CDIR':CE_DIR,'CE_OIP':CE_OIP,'CE_OI':CE_OI,'CE_COI':CE_COI,'CE_vol':CE_vol,'CE_volp':CE_volp,
                        'CE_IV':CE_IV,'CE_LTP':CE_LTP,'CE_chng':CE_chng,'CE_COIP':CE_COIP,'strikePrice':strikePrice,
                        'PE_COIP': PE_COIP,'PE_chng':PE_chng,'PE_LTP':PE_LTP,'PE_IV':PE_IV,'PE_volp':PE_volp,
                        'PE_vol':PE_vol,'PE_COI':PE_COI,'PE_OI': PE_OI,'PE_OIP':PE_OIP, 'PDIR':PE_DIR,'PDIF':P_DIF}
            k+=1
            # print(CE_COI,PE_COI)
            # b = list(range(int(float(P_DIF))))-4
            # print(b)
    


            

    # === to add history CE_OIP and PE_OIP in the result dictionary
    
    today = datetime.now().date()
    if today.isoweekday() == 1:
        today = today-timedelta(days=2)
    elif today.isoweekday() == 7:
        today = today-timedelta(days=1)
    today = today-timedelta(days=1)

    historyRes = HistoryData.objects.filter(stored_date=today, optionType=symbol).values('strikePrice', 'pe_oipd', 'ce_oipd')

    for strike in historyRes:
        if int(float(strike['strikePrice'])) in result:
            result[int(float(strike['strikePrice']))]['pe_oipd'] = strike['pe_oipd']
            result[int(float(strike['strikePrice']))]['ce_oipd'] = strike['ce_oipd']

    # print(historyRes)
    # ---------------------------------------------------------------------
    
    # <==================== TO GET 5 WEEKS PCR values ADDED NEWLY ===============================>
    PCR = {}
    for e in range(5):
        pe = 0
        ce = 0
        for i in range(len(data)):
            if data[i]['expiryDate'] == expiry_dates[e]:
                pe+=data[i]['PE']['openInterest'] if 'PE' in data[i] else 0
                ce+=data[i]['CE']['openInterest'] if 'CE' in data[i] else 0
        PCR[expiry_dates[e]]=float(str(pe/ce if ce !=0 else 0)[:4])
    PCR = [{'e':i, 'pcr':PCR[i]} for i in PCR]

    # <====================== ALSO ADDED PCR IN RETURN STATEMENT =============================>
     
    l1 = sorted(oiList1)[-1:-4:-1] if oiList1 else [[0,0,0]]
    l2 = sorted(oiList2)[-1:-4:-1] if oiList2 else [[0,0,0]]
    l3 = sorted(oiList3)[-1:-4:-1] if oiList3 else [[0,0,0]]
    l4 = sorted(oiList4)[-1:-4:-1] if oiList4 else [[0,0,0]]
    l5 = sorted(coiList1)[-1:-4:-1] if coiList1 else [[0,0,0]]
    l6 = sorted(coiList2)[-1:-4:-1] if coiList2 else [[0,0,0]]
    l7 = sorted(coiList3)[-1:-4:-1] if coiList3 else [[0,0,0]]
    l8 = sorted(coiList4)[-1:-4:-1] if coiList4 else [[0,0,0]]

# ============================================ OI CALL/PUT =================================================
   
    oi23_sum = pd.DataFrame(oiList2).loc[0:6].clip(lower=0).sum(axis=0)[0] + oiList1[-1][-3]
    oi34_sum= pd.DataFrame(oiList3).tail(6).clip(lower=0).sum(axis=0)[0] + oiList4[0][0]
    oitot_sum=(oi34_sum-oi23_sum)
   
    # _____________________________________  COI/CALL/PUT _________________________________   

    coi21_sum = pd.DataFrame(coiList2).loc[0:6].clip(lower=0).sum(axis=0)[0] + coiList1[-1][-3]
    poi34_sum= pd.DataFrame(coiList3).tail(6).clip(lower=0).sum(axis=0)[0] + coiList4[0][0]
    coitot_sum=(coi21_sum-poi34_sum)
  
    # ======================================================================================

    pcr_l3=pd.DataFrame(oiList3).tail(10)
#   ==================================================================
    if l3:
        min_PE_OI = min(l3, key = lambda i:i[1])[1]     
  
    else:
        min_PE_OI = 0
    if l2:
        max_CE_OI = max(l2, key = lambda i:i[1])[1]        
    else:
        max_CE_OI = 0    
    if l7:
        min_PE_COI = min(l7, key = lambda i:i[1])[1]         
    else:
        min_PE_COI = 0
    if l6:
        max_CE_COI = max(l6, key = lambda i:i[1])[1]      
    else:
        max_CE_COI = 0
    
  
    # <======================= GET TOP BOTTOM RANGE FROM THE DB ===============================>


    today = datetime.now().date()    
    if today.isoweekday() == 1:
        today = today-timedelta(days=2)
    elif today.isoweekday() == 7:
        today = today-timedelta(days=1)
    today = today-timedelta(days=1)
    dbResult = HistoryData.objects.filter(stored_date=today, optionType=symbol, strikePrice__range = (min_PE_OI, max_CE_OI,)).values()
     

    # <=================== ADDED NEWLY MAX PAIN ===========================>

    cl1 = sorted(coiList1)[-1:-4:-1] if coiList1 else [[0,0,0]]
    cl2 = sorted(coiList2)[-1:-4:-1] if coiList2 else [[0,0,0]]    
    cl3 = sorted(coiList3)[-1:-4:-1] if coiList3 else [[0,0,0]]
    cl4 = sorted(coiList4)[-1:-4:-1] if coiList4 else [[0,0,0]]   

     
    maxCOI = max(cl1[0], cl2[0])
    maxPOI = max(cl3[0], cl4[0])
    oiList1.extend(oiList2)
    oiList3.extend(oiList4)
    maxPainOI = [{'strikePrice':i[1], 'value':i[0]} for i in sorted(map(lambda i,j:[i[0]+j[0], i[1], i[2]],oiList1, oiList3))[-1:-4:-1]]
    
    # print(maxPainOI)

    # <======================== ADDED IN THE RETURN STATEMENT =====================================>
    
    if len(result)>=3:
        for i in range(3):
          # print(i)
            result[l1[i][1]]['CE_OI_COLOR'] = i+1 
            result[l2[i][1]]['CE_OI_COLOR'] = i+1
           
            result[l3[i][1]]['PE_OI_COLOR'] = i+1
            result[l4[i][1]]['PE_OI_COLOR'] = i+1
            result[cl1[i][1]]['CE_COI_COLOR'] = i+1
            result[cl2[i][1]]['CE_COI_COLOR'] = i+1
            result[cl3[i][1]]['PE_COI_COLOR'] = i+1
            result[cl4[i][1]]['PE_COI_COLOR'] = i+1
            result[maxCOI[1]]['MAX_COI'] = 1
            result[maxPOI[1]]['MAX_POI'] = 1
            result[volList1[2]]['CE_MAX_VOL'] = 1
            result[volList2[2]]['PE_MAX_VOL'] = 1
        
    if symbol == 'NIFTY':
        s = list(range(int(float(NPOM))-8*d, int(float(NPOM))+8*d+1, d))
        j = list(range(int(float(NPOM))-10*d, int(float(NPOM))+10*d+1, d))
        # print(s)
        
    elif symbol == 'FINNIFTY':
        s = list(range(int(float(FNPOM))-8*d, int(float(FNPOM))+8*d+1, d))
        j = list(range(int(float(NPOM))-10*d, int(float(FNPOM))+10*d+1, d))

    else:
        s = list(range(int(float(BNPOM))-8*d, int(float(BNPOM))+8*d+1, d))
        j = list(range(int(float(BNPOM))-10*d, int(float(BNPOM))+10*d+1, d))

# <====================================================================>

    # keys = ['CE_COI', 'PE_COI', 'CE_LTP', 'PE_LTP', 'CE_OI', 'PE_OI', 'CE_OIP', 'PE_OIP', 'CE_COIP', 'PE_COIP', 'CE_volp', 'PE_volp']
    # values = {key: [result[i][key] for i in j] for key in keys}    
    # jr1, jr2, jco1, jpo1 = (values[key] for key in keys)    
    # j1 = sorted(jco1)[-1:-3:-1]
    # jco_stren = sum(jco1)  
    # jpo_stren = sum(jpo1)
    # jcp_strenth = jpo_stren - jco_stren
    # jcoi_stren = sum(jr1)
    # jpoi_stren = sum(jr2)
    # jcpoi_strenth = jpoi_stren - jcoi_stren   

       
#  <====================== GRAPH CODE ==============================>
    
    keys = ['CE_COI', 'PE_COI', 'CE_LTP', 'PE_LTP', 'CE_OI', 'PE_OI', 'CE_OIP', 'PE_OIP', 'CE_COIP', 'PE_COIP', 'CE_volp', 'PE_volp']
    values = {key: [result[i][key] for i in s] for key in keys}

    r1, r2, ltp1, ltp2, co1, po1, cpd1, ppd1, ccpd2, pppd2, vopc, vopp = (values[key] for key in keys)
   
    co_stren=sum(co1)
    po_stren=sum(po1) 
    cp_strenth=(po_stren-co_stren)    
    cpc_strenth=(co_stren-po_stren)    
 
    # <=============== ATM RANGE COI =======================>
    cco_stren=sum(r1)
    ppo_stren=sum(r2)
    cpo_strenth=(ppo_stren-cco_stren)
    cpop_strenth=(cco_stren-ppo_stren)   

#   --------------------------------------
   
    dbResult = HistoryData.objects.filter(stored_date=today, optionType=symbol, strikePrice__range = (current_market_price-4*d, current_market_price+4*d+1)).values()
    historyr1 = [i['CE_OI'] for i in dbResult]
    historyr2 = [i['PE_OI'] for i in dbResult]
    hltp1 = [i['CE_LTP'] for i in dbResult]
    hltp2 = [i['PE_LTP'] for i in dbResult]
    ohist1 = [i['CE_OI'] for i in dbResult]
    ohist2 = [i['PE_OI'] for i in dbResult]

    dbResult1=HistoryData.objects.filter(stored_date=today, optionType=symbol, strikePrice__range = (current_market_price-5*d, current_market_price+5*d+1)).values()
    
#    <===============================================================================================================================================>

     # <============= OI MONTHLY RANGE ======================== >

    OI_analysis_label = []    
    OI_analysis_COI = []
    OI_analysis_POI = []

    for i in sorted(result):
        # print(i)
        if i>=min_PE_COI and i<=max_CE_COI:
            OI_analysis_label.append(result[i]['strikePrice'])
            # print(OI_analysis_label)

            OI_analysis_COI.append(result[i]['CE_COI'])
            OI_analysis_POI.append(result[i]['PE_COI'])
            # print(OI_analysis_POI)

    ccoi_list=sum(OI_analysis_COI)   
    pcoi_list=sum(OI_analysis_POI)
    cepei=pcoi_list-ccoi_list
    
    # print(ccoi_list,pcoi_list)
    
    # print(OI_analysis_POI, OI_analysis_COI,OI_analysis_label)    
             
 
    # <============= OI MONTHLY RANGE ======================== >

    OI_analysis_label = []

    OI_analysis_CE = []
       
    OI_analysis_PE = []

    for i in sorted(result):
        if i>=min_PE_OI and i<=max_CE_OI:
            OI_analysis_label.append(result[i]['strikePrice'])
            OI_analysis_CE.append(result[i]['CE_OI'])
            OI_analysis_PE.append(result[i]['PE_OI'])
            
    # print(OI_analysis_label, OI_analysis_CE, OI_analysis_PE)


    
    # <================= WEEKLY RANGE PCR & STRENTH =====================>

    ce_list=sum(OI_analysis_CE)
   
    pe_list=sum(OI_analysis_PE)
    
    cepe=pe_list-ce_list
    # print(ce_list,pe_list)
    # print(cepe)

    wrp=float(str(pe_list/ce_list if ce_list !=0 else 0)  [:4])
       
    # print(ce_list,pe_list,wrp)
        
    H_dbResult = HistoryData.objects.filter(stored_date=today, optionType=symbol,strikePrice__range=(min_PE_OI,max_CE_OI)).values()
    hdlist1 = [i['CE_OI'] for i in H_dbResult]
    hdlist2 = [i['PE_OI'] for i in H_dbResult]  
   
    coi = {}
    poi = {}
    for i in H_dbResult:
        coi[i['strikePrice']] = 0
        poi[i['strikePrice']] = 0
    
    for i in l6:
        if str(i[1]) in coi:
            coi[str(i[1])] = i[0]
    
    for i in l7:
        if str(i[1]) in poi:
            poi[str(i[1])] = i[0]

    #coi = [i for i in coi]
    coi = list(coi.values())
    
   
    poi = list(poi.values())
    # print(coi, poi, hdlist1, hdlist2, sep = '\n')

    #sending maxpain table data to front-end
    month = datetime.now().date() - timedelta(days=30)
    maxpaintable = MaxPain.objects.filter(stored_date__gte=month)

    fdF = FpdcData.objects.filter(client = 'FII').order_by('-stored_date').values()[:7]
    fdD = FpdcData.objects.filter(client = 'DII').order_by('-stored_date').values()[:7]
    fdC = FpdcData.objects.filter(client = 'CLIENT').order_by('-stored_date').values()[:7]
    fdP = FpdcData.objects.filter(client = 'PRO').order_by('-stored_date').values()[:7]

    # Convert NumPy/pandas types to native Python types for JSON serialization
    def to_native(val):
        import numpy as np
        if isinstance(val, np.generic):
            return val.item()
        if hasattr(val, 'tolist'):
            return val.tolist()
        return val

    # Convert all relevant context variables
    oits = to_native(oitot_sum)
    coits = to_native(coitot_sum)
    labels = to_native(s)
    data1 = to_native(r1)
    data2 = to_native(r2)

    context = {
        'result': list(result.values()) if isinstance(result, dict) else list(result),
        'currentMarketPrice':underlyingValue,
        'middle':middle,
        'maxPainOI':maxPainOI,
        'PCR':PCR,
        'max_ce':max_CE_OI,
        'min_pe':min_PE_OI,
        'optionType':symbol,
        'labels': labels,
        'data1': data1,
        'data2': data2,
        'hdata1':historyr1,
        'hdata2':historyr2,
        'h1':hltp1,
        'h2': hltp2,
        'cltp':ltp1,
        'pltp':ltp2,
        'cop1': co1,
        'pop1': po1,
        'oh1':ohist1,
        'oh2':ohist2,
        'OI_analysis_label':OI_analysis_label,
        'OI_analysis_pe':OI_analysis_PE,
        'OI_analysis_ce':OI_analysis_CE,
        'cd2':cpd1,
        'pd2':ppd1,
        'ccd3':ccpd2,
        'ppd3': pppd2,        'premarket_7days': premarket_7days,
        'Hdlistc': hdlist1,
        'Hdlistp': hdlist2,
        'vop1': vopc,
        'vop2': vopp,
        'NPOM': NPOM,
        'BNPOM': BNPOM,
        'FNPOM': FNPOM,
        'coi': coi,
        'poi': poi,
        'maxpaintable': maxpaintable,
        'wrp': wrp,
        'cps': [cp_strenth],
        'cpos': [cpo_strenth],
        'cps1': [cpc_strenth],
        'cpos1': [cpop_strenth],
        'CEPE': [cepe],
        'CEPEI': [cepei],
        'OI_analysis_label': OI_analysis_label,
        'OI_analysis_poi': OI_analysis_POI,
        'OI_analysis_coi': OI_analysis_COI,
        'cclt': ccoi_list,
        'pclt': pcoi_list,
        'oits': oits,
        'coits': coits,
        'fdF': fdF,
        'fdD': fdD,
        'fdC': fdC,
        'fdp': fdP,
    }
    cache.set(cache_key, context, timeout=60*2)  # cache for 2 minutes
    return render(request, 'app/optionChain.html', context)
    #return render(request,'app/optionChain.html', {'result':result.values(), 'currentMarketPrice':underlyingValue, 'middle':middle, 'maxPainOI':maxPainOI, 'PCR':PCR, 'max_ce':max_CE_OI, 'min_pe':min_PE_OI, 'optionType':symbol, 'labels':s, 'data1':r1, 'data2':r2, 'hdata1':historyr1, 'hdata2':historyr2,'h1':hltp1,'h2': hltp2,'cltp':ltp1,'pltp':ltp2,'cop1': co1, 'pop1': po1, 'oh1':ohist1,'oh2':ohist2,'cd2':cpd1,'pd2':ppd1,})
    #except Exception as e:
     #   return HttpResponse(f'<meta http-equiv="refresh" content="10"><body>{e}Wait! Fetching data from NSE</body>')


# <========================  PRE OPEN CODE =======================>

def index(request):
    pom = PreMarket.objects.get(id = 1)
    NPOM = pom.NPOM
    FNPOM = pom.FNPOM
    BNPOM = pom.BNPOM
   
    return render(request, 'base.html', {'NPOM':NPOM, 'BNPOM':BNPOM,'FNPOM': FNPOM,})


def nifty(request, symbol):
    try:
        url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbols[symbol]}'  
        response = requests.get(url, headers=headers, timeout=10)
        response_text = response.text
        json_object = json.loads(response_text)
        records = json_object['records']
        expiry_date = records['expiryDates']
        expiryDate = expiry_date[0]
        expiry_dates = [{'expiry_date':i} for i in expiry_date]
        pom = PreMarket.objects.get(id = 1)
        NPOM = pom.NPOM
        BNPOM = pom.BNPOM
        FNPOM = pom.FNPOM
        return render(request, 'app/nifty.html', {'expiry_dates':expiry_dates, 'symbol':{'symbol':symbols[symbol]}, 'expiryDate':{'expiryDate':expiryDate}, 'NPOM':NPOM, 'BNPOM':BNPOM,'FNPOM': FNPOM})
    except Exception as e:
        return HttpResponse(f'<meta http-equiv="refresh" content="60"><body>{e}Wait! Fetching data from NSE</body>')


# <=============== HISTORY DATA CODE ====================>

def historyDataGet(request, symbol, expiryDate):
    expiryDate = datetime.strptime(expiryDate, '%d-%b-%Y').date()
    pom = PreMarket.objects.get(id = 1)
    NPOM = pom.NPOM
    BNPOM = pom.BNPOM
    FNPOM = pom.FNPOM
    #d = expiryDate-datetime.now().date()
    # print(expiryDate, symbol, 6-d.days)

    if symbol == 'NIFTY':
        day6 = expiryDate
        # print(day6)
        day5 = expiryDate-timedelta(days=1)
        # print(day5)
        day4 = expiryDate-timedelta(days=2)
        # print(day4)
        day3 = expiryDate-timedelta(days=3)
        # print(day3)
        day2 = expiryDate-timedelta(days=6)
        # print(day2)
        day1 = expiryDate-timedelta(days=7)
        # print(day1)
    if symbol == 'BANKNIFTY':
        day6 = expiryDate
        day5 = expiryDate-timedelta(days=1)
        day4 = expiryDate-timedelta(days=2)
        day3 = expiryDate-timedelta(days=5)
        day2 = expiryDate-timedelta(days=6)
        day1 = expiryDate-timedelta(days=7)
    if symbol == 'FINNIFTY':
        day6 = expiryDate
        day5 = expiryDate-timedelta(days=1)
        day4 = expiryDate-timedelta(days=2)
        day3 = expiryDate-timedelta(days=5)
        day2 = expiryDate-timedelta(days=6)
        day1 = expiryDate-timedelta(days=7)

    day6_data = HistoryData.objects.filter(optionType=symbol, stored_date=day6)    
    day5_data = HistoryData.objects.filter(optionType=symbol, stored_date=day5) 
    day4_data = HistoryData.objects.filter(optionType=symbol, stored_date=day4) 
    day3_data = HistoryData.objects.filter(optionType=symbol, stored_date=day3)     
    day2_data = HistoryData.objects.filter(optionType=symbol, stored_date=day2)  
    day1_data = HistoryData.objects.filter(optionType=symbol, stored_date=day1)
        
  
    result = {}
    for d in day1_data.values():
        result[d['strikePrice']] = d
    
    i = 2
    for day in [day2_data, day3_data, day4_data, day5_data, day6_data]:
        top = []
        if i == 2:
            j = ''
        else:
            j = i-1

        for sp in day.values():
            strikePrice = sp['strikePrice']
            PE_OI = sp['PE_OI']
            PE_LTP = sp['PE_LTP']
            CE_OI = sp['CE_OI']
            CE_LTP = sp['CE_LTP']

            # if strikePrice in result:
            #     #GET FROM ORIGINAL
            #     PE_OI_ORG = result[strikePrice][f'PE_OI{j}']
            #     CE_OI_ORG = result[strikePrice][f'CE_OI{j}']
            #     PE_LTP_ORG = result[strikePrice][f'PE_LTP{j}']
            #     CE_LTP_ORG = result[strikePrice][f'CE_LTP{j}']
            if strikePrice in result:
                # Use .get() to avoid KeyError if the key does not exist
                PE_OI_ORG = result[strikePrice].get(f'PE_OI{j}', 0)
                CE_OI_ORG = result[strikePrice].get(f'CE_OI{j}', 0)
                PE_LTP_ORG = result[strikePrice].get(f'PE_LTP{j}', 0)
                CE_LTP_ORG = result[strikePrice].get(f'CE_LTP{j}', 0)
            else:
                result[strikePrice] = {'strikePrice': strikePrice}
                PE_OI_ORG = 0
                CE_OI_ORG = 0
                PE_LTP_ORG = 0
                CE_LTP_ORG = 0

            #STORE INTO ORIGINAL
            result[strikePrice][f'PE_OI{i}'] = PE_OI
            result[strikePrice][f'PE_OID{i}'] = round(PE_OI-PE_OI_ORG)
            result[strikePrice][f'CE_OI{i}'] = CE_OI
            result[strikePrice][f'CE_OID{i}'] = round(CE_OI-CE_OI_ORG)
            result[strikePrice][f'PE_LTP{i}'] = PE_LTP
            result[strikePrice][f'PE_LTPD{i}'] = round(PE_LTP-PE_LTP_ORG)
            result[strikePrice][f'CE_LTP{i}'] = CE_LTP
            result[strikePrice][f'CE_LTPD{i}'] = round(CE_LTP-CE_LTP_ORG)
            top.append([strikePrice, PE_OI-PE_OI_ORG, CE_OI-CE_OI_ORG, PE_LTP-PE_LTP_ORG, CE_LTP-CE_LTP_ORG])
        
        
        topPEDOI = sorted(top, key = lambda i:i[1])[-3:]
        print(topPEDOI)
        topCEDOI = sorted(top, key = lambda i:i[2])[-3:]
        topPEDLPT = sorted(top, key = lambda i:i[3])[-3:]
        topPEDLPTN = sorted(top, key = lambda i:i[3])[:3]
        topCEDLPT = sorted(top, key = lambda i:i[4])[-3:]
        topCEDLPTN = sorted(top, key = lambda i:i[4])[:3]

        vartop = [f'topPEDOI{i}', f'topCEDOI{i}', f'topPEDLPT{i}', f'topPEDLPTN{i}', f'topCEDLPT{i}', f'topCEDLPTN{i}']
        k = 0
        for tops in [topPEDOI, topCEDOI, topPEDLPT, topPEDLPTN, topCEDLPT, topCEDLPTN]:
            for t in tops:
                strP = t[0]
                result[strP][vartop[k]] = 1
            k+=1
        i+=1


    return render(request, 'app/history.html', {'result':result.values(), 'day1':day1.strftime('%A'), 'day2':day2.strftime('%A'), 'day3':day3.strftime('%A'), 'day4':day4.strftime('%A'), 'day5':day5.strftime('%A'), 'day6':day6.strftime('%A')})
    #return render(request, 'app/history.html', {'day1':day1, 'day2':day2, 'day3':day3, 'day4':day4, 'day5':day5, 'day6':day6, 
    #'day6_data':day6_data, 'day5_data':day5_data, 'day4_data':day4_data, 'day3_data':day3_data, 'day2_data':day2_data, 'day1_data':day1_data})
    #return HttpResponse(f'<body>data from history</body>')



#to convert date from dd-mon-yyyy format
#import datetime
#datetime.datetime.strptime('10-sep-2023', '%d-%b-%Y').date()
#create function to store the latest OI and LTP values

# <============== STORE DATA MANUALLY ============>

def storeHistoryData(symbol):

    url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
    
    response = requests.get(url, headers=headers, timeout=10)
    response_text = response.text
    json_object = json.loads(response_text)
    records = json_object['records']
    
    data = records['data']
    expiry_date = records['expiryDates'][0]
    underlyingValue = records['underlyingValue']

    expiryDate = datetime.strptime(expiry_date, '%d-%b-%Y').date()

    current_market_price = round(float(underlyingValue))
    samp = int(str(current_market_price)[-2:])

    
    if symbol== 'BANKNIFTY':
        current_market_price = current_market_price-samp+100
    else:        
        if samp>=50:
            current_market_price = current_market_price-samp+100
        else:
            current_market_price = current_market_price-samp+50
    
    #to get strike prices 25 top and bottom
    if symbol == 'BANKNIFTY':
        d = 100
    else:
        d = 50
    s = set(range(current_market_price-25*d, current_market_price+25*d+1, d))
  


    # for i in range(len(data)):
    #     if data[i]['expiryDate'] == expiry_date and data[i]['strikePrice'] in s:
    #         peCOI=data[i]['PE']['changeinOpenInterest']
    #         pOI=data[i]['PE']['openInterest']
    #         cOI=data[i]['CE']['openInterest']
    #         ceCOI=data[i]['CE']['changeinOpenInterest']
    #         peLTP = data[i]['PE']['lastPrice']
    #         ceLTP = data[i]['CE']['lastPrice']
    #         strikePrice = data[i]['CE']['strikePrice']
    #         if 'CE' in data[i]:
    #             # CE_OI = (data[i]['CE']['openInterest'])
    #             CE_OI = data[i]['CE']['openInterest'] if data[i]['CE']['openInterest'] != 0 else 1                
    #         else:
    #             CE_OI=0

    #         if 'PE' in data[i]:
    #             # PE_OI = data[i]['PE']['openInterest']
    #             PE_OI = data[i]['PE']['openInterest'] if data[i]['PE']['openInterest'] != 0 else 1
    #         else:
    #             PE_OI=0
    #         OI_total = CE_OI+PE_OI
    #         CE_OIP = round((CE_OI/OI_total)*100, 1) if CE_OI !=0 else 0
           
    #         PE_OIP = round((PE_OI/OI_total)*100, 1) if OI_total !=0 else 0
    
    #         dataInsert = HistoryData(strikePrice=strikePrice,expiryDate=expiryDate, PE_COI = peCOI, CE_COI = ceCOI, PE_LTP =peLTP, CE_LTP = ceLTP, CE_OI=cOI, PE_OI=pOI, optionType=symbol,stored_date=datetime.now().date(), ce_oipd=CE_OIP,  pe_oipd= PE_OIP)
    #         dataInsert.save()
    for i in range(len(data)):            
            if data[i]['expiryDate'] == expiry_date:
                peCOI = data[i]['PE']['changeinOpenInterest']
                pOI = data[i]['PE']['openInterest']
                cOI = data[i]['CE']['openInterest']
                ceCOI = data[i]['CE']['changeinOpenInterest']
                peLTP = data[i]['PE']['lastPrice']
                ceLTP = data[i]['CE']['lastPrice']
                strikePrice = data[i]['CE']['strikePrice']
                if 'CE' in data[i]:
                    CE_OI = data[i]['CE']['openInterest'] if data[i]['CE']['openInterest'] != 0 else 1                
                else:
                    CE_OI = 0
        
                if 'PE' in data[i]:
                    PE_OI = data[i]['PE']['openInterest'] if data[i]['PE']['openInterest'] != 0 else 1
                else:
                    PE_OI = 0
                OI_total = CE_OI + PE_OI
                CE_OIP = round((CE_OI / OI_total) * 100, 1) if CE_OI != 0 else 0
                PE_OIP = round((PE_OI / OI_total) * 100, 1) if OI_total != 0 else 0
        
                dataInsert = HistoryData(
                    strikePrice=strikePrice,
                    expiryDate=expiryDate,
                    PE_COI=peCOI,
                    CE_COI=ceCOI,
                    PE_LTP=peLTP,
                    CE_LTP=ceLTP,
                    CE_OI=cOI,
                    PE_OI=pOI,
                    optionType=symbol,
                    stored_date=datetime.now().date(),
                    ce_oipd=CE_OIP,
                    pe_oipd=PE_OIP
                )
                dataInsert.save()    


def manullyStoreHistoryData():
    storeHistoryData('NIFTY')
    storeHistoryData('BANKNIFTY')
    storeHistoryData('FINNIFTY')


#REMOVE COMMENT FOR THE BELOW FUNCTION and restart the server TO STORE HISTORY DATA MANUALLY 
# manullyStoreHistoryData()



def sample(request):
    if datetime.now().strftime('%A')not in  {'saturday','Sunday'}:
        today = datetime.now().date()
        if datetime.now().hour >19.30:
            n = HistoryData.objects.filter(stored_date=today, optionType='NIFTY')
            b = HistoryData.objects.filter(stored_date=today, optionType='BANKNIFTY')
            f = HistoryData.objects.filter(stored_date=today, optionType='FINNIFTY')
        elif datetime.now().hour<=9:
            if today.isoweekday() == 1:
                temp_today = today-timedelta(days=2)
            else:
                temp_today = today
            n = HistoryData.objects.filter(stored_date=temp_today-timedelta(days=1), optionType='NIFTY')
            b = HistoryData.objects.filter(stored_date=temp_today-timedelta(days=1), optionType='BANKNIFTY')
            f = HistoryData.objects.filter(stored_date=temp_today-timedelta(days=1), optionType='FINNIFTY')
        if not n:
            storeHistoryData('NIFTY')
            print('Nifty Date stored')
            if datetime.now().hour<=9:
                HistoryData.objects.filter(stored_date=today, optionType='NIFTY').update(stored_date = temp_today-timedelta(days=1))
        if not b:
            storeHistoryData('BANKNIFTY')
            print('BankNifty Date stored')
            if datetime.now().hour<=9:
                HistoryData.objects.filter(stored_date=today, optionType='BANKNIFTY').update(stored_date = temp_today-timedelta(days=1))
        if not f:
            storeHistoryData('FINNIFTY')
            print('FinNifty Date stored')
            if datetime.now().hour<=9:
                HistoryData.objects.filter(stored_date=today, optionType='FINNIFTY').update(stored_date = temp_today-timedelta(days=1))
    
    return redirect('index')


# <================== DELETE PREVIOUS HISTORY DATA ========================>

def housekeepingfun():
    today = datetime.now()
    day = today.isoweekday()
    if day == 4 and today.hour>22 and HistoryData.objects.filter(optionType='NIFTY', stored_date__lt =  datetime.now().date()):
        HistoryData.objects.filter(optionType='NIFTY', stored_date__lt =  datetime.now().date()).delete()
    if day == 3 and today.hour>22 and HistoryData.objects.filter(optionType='BANKNIFTY', stored_date__lt =  datetime.now().date()):
        HistoryData.objects.filter(optionType='BANKNIFTY', stored_date__lt =  datetime.now().date()).delete()
    if day == 2 and today.hour>22 and HistoryData.objects.filter(optionType='FINNIFTY', stored_date__lt =  datetime.now().date()):
        HistoryData.objects.filter(optionType='FINNIFTY', stored_date__lt =  datetime.now().date()).delete()

def houseKeeping(requests):
    housekeepingfun()
    return redirect('index')


housekeepingfun()


#  <======================= STORE DATA MANUALLY ==========================>


def storeDataManually(request):

    path = r"C:\Users\HAI\Desktop\DATAFILES"            
    #path = r"C:\Users\HP\Downloads\CSV"
    files = os.listdir(path)
    symbol = ''
    for f in files:
        if 'B' in f:
            symbol = 'BANKNIFTY'
        elif 'F' in f:
            symbol = 'FINNIFTY'
        else:
            symbol = 'NIFTY'

        url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
        
        response = requests.get(url, headers=headers, timeout=10)
        response_text = response.text
        json_object = json.loads(response_text)
        records = json_object['records']
        
        data = records['data']
        expiry_date = records['expiryDates'][0]
        underlyingValue = records['underlyingValue']

        expiryDate = datetime.strptime(expiry_date, '%d-%b-%Y').date()

        current_market_price = round(float(underlyingValue))
        samp = int(str(current_market_price)[-2:])

        
        if symbol== 'BANKNIFTY':
            current_market_price = current_market_price-samp+100
        else:        
            if samp>=50:
                current_market_price = current_market_price-samp+100
            else:
                current_market_price = current_market_price-samp+50
        
        #to get strike prices 25 top and bottom
        if symbol == 'BANKNIFTY':
            d = 100
        else:
            d = 50
        s = set(range(current_market_price-25*d, current_market_price+25*d+1, d))
        #print(expiry_date)
        expiry_date = datetime.strptime(expiry_date, '%d-%b-%Y')
        storeddate = datetime.strptime(f[:11], '%d-%b-%Y').date()
        storeDataManuallyFun(path, f, symbol, expiry_date, s, storeddate)
        os.remove(path+"\\"+f)
    return redirect('index')



    
def storeDataManuallyFun(path, file, symbol, expiry_date, s, storeddate):
  
    df = pd.read_csv(path+"\\"+file, usecols = ['STRIKE', 'OI', 'CHNG IN OI', 'LTP',  'OI.1', 'CHNG IN OI.1', 'LTP.1'], header = 1).values
    #print(symbol)
    for data in df:
        if int(locale.atof(data[3])) in s:
            peCOI=locale.atof(data[5]) if data[5] != '-' else 0
            pOI=locale.atof(data[6]) if data[6] != '-' else 0
            cOI=locale.atof(data[0]) if data[0] != '-' else 0
            ceCOI=locale.atof(data[1]) if data[1] != '-' else 0
            peLTP = locale.atof(data[4]) if data[4] != '-' else 0
            ceLTP = locale.atof(data[2]) if data[2] != '-' else 0
            strikePrice = int(locale.atof(data[3]))
            dataInsert = HistoryData(strikePrice=strikePrice,expiryDate=expiryDate, PE_COI = peCOI, CE_COI = ceCOI, PE_LTP =peLTP, CE_LTP = ceLTP, CE_OI=cOI, PE_OI=pOI, optionType=symbol,stored_date = storeddate)
            dataInsert.save()


# <============================ ALL IN ONE FRAME =============================>


def alloptionChains(request):

    all_result = []
    for symbol in {'NIFTY', 'BANKNIFTY',}: #symbols..values():
        url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
        response = requests.get(url, headers=headers, timeout=10)
        response_text = response.text
        json_object = json.loads(response_text)
        records = json_object['records']
        filtered = json_object['filtered']
        expiry_dates = records['expiryDates']
        expiry_date = expiry_dates[0]
        underlyingValue = records['underlyingValue']
        #store the above expiry dates in the data list. based on that we get the values of the market.
        data = records['data']
        #to get current market price with rounded strike prices
        current_market_price = round(float(underlyingValue))
        samp = int(str(current_market_price)[-2:])
    
        if symbol== 'BANKNIFTY':
            current_market_price = current_market_price-samp+100
        else:        
            if samp>=50:
                current_market_price = current_market_price-samp+100
            else:
                current_market_price = current_market_price-samp+50
        middle = current_market_price

        #to get strike prices 25 top and bottom
        if symbol == 'BANKNIFTY':
            d = 100
        else:
            d = 50
        s = set(range(current_market_price-7*d, current_market_price+7*d+1, d))
        # print(s)

        result = {}
        k = 0

        oiList1 = []
        oiList2 = []
        oiList3 = []
        oiList4 = []

        for i in range(len(data)):
            if data[i]['strikePrice'] in s and data[i]['expiryDate'] == expiry_date:
                if 'CE' in data[i]:
                    CE_OI = data[i]['CE']['openInterest']
                    CE_COI = data[i]['CE']['changeinOpenInterest']
                    strikePrice1 = data[i]['CE']['strikePrice']
                else:
                    CE_OI=CE_COI=CE_vol=CE_IV=CE_LTP=CE_chng=strikePrice1=0

                if 'PE' in data[i]:
                    PE_COI = data[i]['PE']['changeinOpenInterest']
                    PE_OI = data[i]['PE']['openInterest']
                    strikePrice2 = data[i]['PE']['strikePrice']
                else:
                    PE_OI=PE_COI=PE_vol=PE_chng=PE_LTP=PE_IV=strikePrice2=0
                strikePrice = max(strikePrice1, strikePrice2)        
                COI_total = CE_COI+PE_COI
                OI_total = CE_OI+PE_OI
            
                CE_OIP = round((CE_OI/OI_total)*100, 1) if CE_OI !=0 else 0
                PE_OIP = round((PE_OI/OI_total)*100, 1) if OI_total !=0 else 0
                CE_COIP = round((CE_COI/COI_total)*100, 1) if COI_total !=0 else 0
                PE_COIP = round((PE_COI/COI_total)*100, 1) if COI_total !=0 else 0
                
                if data[i]['strikePrice'] < underlyingValue:
                    oiList1.append([CE_OI, data[i]['strikePrice'], k])
                    oiList3.append([PE_OI, data[i]['strikePrice'], k])
                else:
                    oiList2.append([CE_OI, data[i]['strikePrice'], k])
                    oiList4.append([PE_OI, data[i]['strikePrice'], k])


                result[strikePrice] = {'CE_OIP':CE_OIP,'CE_COIP':CE_COIP,'strikePrice':strikePrice,'PE_COIP': PE_COIP,'PE_OIP':PE_OIP}
                k+=1
        
       #<========================== TO GET 5 weeks PCR values ADDED NEWLY =========================>

        PCR = {}
        for e in range(5):
            pe = 0
            ce = 0
            for i in range(len(data)):
                if data[i]['expiryDate'] == expiry_dates[e]:
                    pe+=data[i]['PE']['openInterest'] if 'PE' in data[i] else 0
                    ce+=data[i]['CE']['openInterest'] if 'CE' in data[i] else 0
            PCR[expiry_dates[e]]=float(str(pe/ce if ce !=0 else 0)[:4])
        PCR = [{'e':i, 'pcr':PCR[i]} for i in PCR]

        
        l1 = sorted(oiList1)[-1:-4:-1] if oiList1 else [[0,0,0]]
        l2 = sorted(oiList2)[-1:-4:-1] if oiList2 else [[0,0,0]]
        l3 = sorted(oiList3)[-1:-4:-1] if oiList3 else [[0,0,0]]
        l4 = sorted(oiList4)[-1:-4:-1] if oiList4 else [[0,0,0]]

        oiList1.extend(oiList2)
        oiList3.extend(oiList4)
        maxPainOI = [{'strikePrice':i[1], 'value':i[0]} for i in sorted(map(lambda i,j:[i[0]+j[0], i[1], i[2]],oiList1, oiList3))[-1:-4:-1]]

        today = datetime.now()
        day = today.isoweekday()
        
        if day not in (6, 1) and today.hour>18 and not MaxPain.objects.filter(optionType = symbol, stored_date = datetime.now().date()):
            for i in maxPainOI:
                if i['strikePrice']>underlyingValue:
                    s = 'r'
                else:
                    s = 's'
                MaxPain.objects.create(val = i['strikePrice'], sr = s, stored_date = datetime.now().date(), optionType = symbol)


        # print(maxPainOI)
        all_result.append({'result':result.values(), 'maxPainOI':maxPainOI, 'PCR':PCR, 'optionType':symbol, 'middle':middle, 'currentMarketPrice':underlyingValue})

        pom = PreMarket.objects.get(id = 1)
        NPOM = pom.NPOM
        BNPOM = pom.BNPOM
        FNPOM = pom.FNPOM


        pod = PreMarketData.objects.get(id = 1)
        NPOD = pod. N_Open
        NPCD = pod. N_Close
        NPHD = pod. N_High
        NPLD = pod. N_Low
       


    return render(request,'app/multichart.html', {'all_result':all_result, 'NPOM':NPOM, 'BNPOM':BNPOM,'FNPOM':FNPOM,'NPOD':NPOD,'NPCD':NPCD,'NPHD':NPHD,'NPLD':NPLD})
    #return render(request,'app/optionChain.html', {'result':result.values(), 'currentMarketPrice':underlyingValue, 'middle':middle, 'maxPainOI':maxPainOI, 'PCR':PCR, 'max_ce':max_CE_OI, 'min_pe':min_PE_OI, 'optionType':symbol, 'labels':s, 'data1':r1, 'data2':r2, 'hdata1':historyr1, 'hdata2':historyr2,'h1':hltp1,'h2': hltp2,'cltp':ltp1,'pltp':ltp2,'cop1': co1, 'pop1': po1, 'oh1':ohist1,'oh2':ohist2,'cd2':cpd1,'pd2':ppd1,})
    #except Exception as e:
     #   return HttpResponse(f'<meta http-equiv="refresh" content="10"><body>{e}Wait! Fetching data from NSE</body>')


def preOpenMarket(request):
    form = PreMarketForm()
    return render(request, 'app/preOpenMarket.html', {'form':form})


def preOpenMarketAction(request):
    if request.method == 'POST':
        form = PreMarketForm(request.POST)
        if form.is_valid():
            pm = PreMarket.objects.get(id = 1)
            pm.NPOM = form.cleaned_data['NPOM']
            pm.BNPOM = form.cleaned_data['BNPOM']
            pm.FNPOM = form.cleaned_data['FNPOM']
            pm.save()
        return redirect('index')
    else:
        form = PreMarketForm()
    return render(request, 'app/preOpenMarket.html', {'form': form})

#  <======================= STORE DATA MANUALLY from FII==========================>


def FiiData(request):

    path = r"C:\Users\HAI\OneDrive\Desktop\DATAFILES"            
    files = os.listdir(path)
    for file in files:
        # Skip system files and non-data files
        if os.path.isdir(os.path.join(path, file)) or not file.lower().endswith('.csv'):
            continue
        try:
            storeddate = datetime.strptime(file[:11], '%d-%b-%Y').date()
        except ValueError:
            # Skip files that don't start with a date
            continue
        Fii(path, file, storeddate)
        os.remove(os.path.join(path, file))
    return redirect('index')
    
# def FiiData(request):
#     path = r"C:\Users\HAI\OneDrive\Desktop\DATAFILES"
#     files = os.listdir(path)
#     for file in files:
#         # Skip system files and non-data files
#         if os.path.isdir(os.path.join(path, file)) or not file.lower().endswith('.csv'):
#             continue
#         try:
#             storeddate = datetime.strptime(file[:11], '%d-%b-%Y').date()
#         except ValueError:
#             # Skip files that don't start with a date
#             continue
#         Fii(path, file, storeddate)
#         os.remove(os.path.join(path, file))
#     return redirect('index')

def Fii(path, file, storeddate):
    # Read the CSV without usecols, then strip all column names
    df = pd.read_csv(path + "\\" + file, header=1)
    df.columns = df.columns.str.strip()
    # Now select the columns you need (after stripping) - use a list, not a set
    df = df[[
        'Client Type',
        'Future Index Long',
        'Future Index Short',
        'Future Stock Long',
        'Future Stock Short',
        'Option Index Call Long',
        'Option Index Put Long',
        'Option Index Call Short',
        'Option Index Put Short'
    ]].values

    for data in df:
        Client_type = data[0].upper()
        Fuind_long = int(data[1])
        Fuind_short = int(data[2])
        Fustk_long =  int(data[3]) 
        Fustk_short = int(data[4])
        Opind_clong = int(data[5])
        Opind_plong = int(data[6])
        Opind_cshort= int(data[7])
        Opind_pshort= int(data[8])
        dataInsert =  FpdcData(client = Client_type,Fut_Index_Long = Fuind_long, Fut_Index_Short = Fuind_short,Fut_Stock_Long = Fustk_long ,
                      Fut_Stock_Short=Fustk_short,Opt_IndeX_CallLong = Opind_clong, Opt_Index_PutLong = Opind_plong,
                      Opt_Index_CallShort=Opind_cshort,Opt_Index_PutShort = Opind_pshort,stored_date=storeddate)
        dataInsert.save()
       

# <===================================== FII PRO DATA ==============================================>


def FiiGet(request, client_type):
    data = FpdcData.objects.filter(client=client_type).order_by('stored_date')
    result = [{'FIL':0, 'FIS':0,}]
    for i in range(len(data)):
        date=data[i].stored_date
        Future_Net_Long = data[i].Fut_Index_Long-result[i]['FIL']
        # print(Future_Net_Long)
        Future_Net_Short = data[i].Fut_Index_Short-result[i]['FIS']
        Net_Call_INDEX = data[i].Opt_IndeX_CallLong - data[i].Opt_Index_CallShort
        Net_Put_INDEX = data[i].Opt_Index_PutLong - data[i].Opt_Index_PutShort
        Net_OI_positions_Options = Net_Call_INDEX - Net_Put_INDEX
        NET_Positions_Future = data[i].Fut_Index_Long - data[i].Fut_Index_Short
        nifty = ''
        long = float(str(Future_Net_Long/data[i].Fut_Index_Long*100)[0:4])
        short = float(str(Future_Net_Short/data[i].Fut_Index_Short*100)[0:4])
        stock_future = data[i].Fut_Stock_Long - data[i].Fut_Stock_Short
        ls = float(str (data[i].Fut_Index_Long/data[i].Fut_Index_Short)[0:4])
        nfno = (NET_Positions_Future+Net_OI_positions_Options)
        result.append({'sd':data[i].stored_date, 'FIL': data[i].Fut_Index_Long, 'FIS': data[i].Fut_Index_Short, 'FSL': data[i].Fut_Stock_Long, 'FSS': data[i].Fut_Stock_Short, 
        'OICL': data[i].Opt_IndeX_CallLong, 'OIPL': data[i].Opt_Index_PutLong, 'OIPS': data[i].Opt_Index_CallShort, 'OICS': data[i].Opt_Index_PutShort, 'FNL': Future_Net_Long, 'FNS': Future_Net_Short,
        'NCI': Net_Call_INDEX, 'NPI': Net_Put_INDEX, 'NOPO': Net_OI_positions_Options, 'NPF': NET_Positions_Future, 'n':nifty, 'long': long, 'short': short, 'sf': stock_future, 'ls':ls, 'nfno':nfno})
        
        
    return render(request, 'app/fii.html', {'data': result,'fnlo':[Future_Net_Long],'fnso':[Future_Net_Short],'date':date,})

fuis=FpdcData.objects.values_list('Fut_Index_Short')
fuil=FpdcData.objects.values_list('Fut_Index_Long')
# print(fuis,fuil)


def futureData(request):
    path = r"C:\Users\HAI\OneDrive\Desktop\DATAFILES"            
  
    # path = r"C:\Users\HP\Downloads\CSV"
    files = os.listdir(path)
    for file in files:
        future(path, file)
        os.remove(path+"\\"+file)
    return redirect('index')


def future(path, file):
    df = pd.read_csv(path+"\\"+file, usecols = ['DATE ','EXPIRY DATE ','SETTLE PRICE ','OPEN INTEREST ','CHANGE IN OI '])
    df["DATE "] = pd.to_datetime(df["DATE "])
    for data in df.sort_values(by='DATE ').values:
   
       
        storedDate = data[0].date()
        exp_date = datetime.strptime(data[1], '%d-%b-%Y').date()
        set_price = float(''.join([i for i in data[2] if i!=',']))
        open_int =  int(''.join([i for i in data[3] if i!=','])) 
        chng_in_oi = int(''.join([i for i in data[4] if i!=',']))
        spot_price = ''
        days = 1
        while days<=4:
            obj = FutData.objects.filter(stored_date = storedDate-timedelta(days=days))
            if obj:
                break
            days+=1
        # print(storedDate, obj.values(), days)
        change_in_sp = round(set_price - (obj[0].set_price if obj else 0), 1)
        #change_in_spot = round(spot_price - (obj[0].spot_price if obj else 0), 1)
        #dataInsert= FutData( set_price = SETTLE  )
      
        dataInsert =  FutData(stored_date = storedDate, exp_date = exp_date, set_price = set_price, open_int = open_int, chng_in_oi = chng_in_oi, chng_in_set_price = change_in_sp)
        dataInsert.save() 


# def futureGet(request):
    
#     fdF = FpdcData.objects.filter(client = 'FII').order_by('-stored_date').values()[:7]
#     fdD = FpdcData.objects.filter(client = 'DII').order_by('-stored_date').values()[:7]
#     fdC = FpdcData.objects.filter(client = 'CLIENT').order_by('-stored_date').values()[:7]
#     fdP = FpdcData.objects.filter(client = 'PRO').order_by('-stored_date').values()[:7]
    
#     return render(request, 'app/future.html', {'fdF': fdF, 'fdD': fdD, 'fdC': fdC, 'fdp': fdP})        

def futureConclusion(request):
    
    obj = FutData.objects.all().order_by('-stored_date')
    # obj = FutData.objects.all().order_by('-stored-date')
    return render(request, 'app/futureConclusion.html', {'fut':obj})
    
    
def fpdcStrength(request):
    data = FpdcData.objects.all().order_by('-stored_date')
    result = {}
    for i in range(len(data)):
        date = data[i].stored_date
        Net_Call_INDEX = data[i].Opt_IndeX_CallLong - data[i].Opt_Index_CallShort
        Net_Put_INDEX = data[i].Opt_Index_PutLong - data[i].Opt_Index_PutShort
        Net_OI_positions_Options = Net_Call_INDEX - Net_Put_INDEX
        NET_Positions_Future = data[i].Fut_Index_Long - data[i].Fut_Index_Short
        client_type = data[i].client
        days = 1
        while days <= 4:
            obj = FpdcData.objects.filter(stored_date=date - timedelta(days=days), client=client_type)
            if obj:
                break
            days += 1
        if obj:
            Y_Net_Call_INDEX = obj[0].Opt_IndeX_CallLong - obj[0].Opt_Index_CallShort
            Y_Net_Put_INDEX = obj[0].Opt_Index_PutLong - obj[0].Opt_Index_PutShort
            Y_Net_OI_positions_Options = Y_Net_Call_INDEX - Y_Net_Put_INDEX
            change_in_NOPO = round(Net_OI_positions_Options - Y_Net_OI_positions_Options, 1)
            change_in_NPF = round(NET_Positions_Future - (obj[0].Fut_Index_Long - obj[0].Fut_Index_Short), 1)
        else:
            change_in_NOPO = 0
            change_in_NPF = 0
        if date not in result:
            result[date] = {'date': date, 'client_type1': client_type, 'NOPO1': Net_OI_positions_Options, 'NPF1': NET_Positions_Future, 'CNOPO1': change_in_NOPO, 'CNPF1': change_in_NPF}
        else:
            for i in range(2, 5):
                if 'client_type' + str(i) not in result[date]:
                    result[date]['client_type' + str(i)] = client_type
                    result[date]['NOPO' + str(i)] = Net_OI_positions_Options
                    result[date]['NPF' + str(i)] = NET_Positions_Future
                    result[date]['CNOPO' + str(i)] = change_in_NOPO
                    result[date]['CNPF' + str(i)] = change_in_NPF
                    break

    # --- Chart Data Preparation ---
    # Prepare chart data for 60 days for FII, DII, CLIENT, PRO
    today = timezone.now().date()
    start_date = today - timedelta(days=60)
    clients = ['FII', 'DII', 'CLIENT', 'PRO']
    chart_data = {
        'FII': {'NOPO': [], 'NPF': []},
        'DII': {'NOPO': [], 'NPF': []},
        'CLIENT': {'NOPO': [], 'NPF': []},
        'PRO': {'NOPO': [], 'NPF': []},
    }
    date_range = [today - timedelta(days=i) for i in range(20, -1, -1)]
    chart_dates = [d.strftime('%Y-%m-%d') for d in date_range]
    for client in clients:
        data_c = FpdcData.objects.filter(client=client, stored_date__range=(start_date, today)).order_by('stored_date')
        data_map = {d.stored_date: d for d in data_c}
        prev_NOPO = prev_NPF = None
        for d in date_range:
            entry = data_map.get(d)
            if entry:
                Net_Call_INDEX = entry.Opt_IndeX_CallLong - entry.Opt_Index_CallShort
                Net_Put_INDEX = entry.Opt_Index_PutLong - entry.Opt_Index_PutShort
                Net_OI_positions_Options = Net_Call_INDEX - Net_Put_INDEX
                NET_Positions_Future = entry.Fut_Index_Long - entry.Fut_Index_Short
                if prev_NOPO is not None:
                    change_in_NOPO = round(Net_OI_positions_Options - prev_NOPO, 1)
                    change_in_NPF = round(NET_Positions_Future - prev_NPF, 1)
                else:
                    change_in_NOPO = 0
                    change_in_NPF = 0
                prev_NOPO = Net_OI_positions_Options
                prev_NPF = NET_Positions_Future
            else:
                change_in_NOPO = 0
                change_in_NPF = 0
            chart_data[client]['NOPO'].append(change_in_NOPO)
            chart_data[client]['NPF'].append(change_in_NPF)
    return render(request, 'app/fpdcStrength.html', {
        'data': result.values(),
        'fpdc_chart_dates': chart_dates,
        'fpdc_chart_data': chart_data
    })

def fpdcStrength_chart(request):
    today = timezone.now().date()
    start_date = today - timedelta(days=60)
    clients = ['FII', 'DII', 'CLIENT', 'PRO']

    # Prepare data dict
    chart_data = {
        'FII': {'NOPO': [], 'NPF': []},
        'DII': {'NOPO': [], 'NPF': []},
        'CLIENT': {'NOPO': [], 'NPF': []},
        'PRO': {'NOPO': [], 'NPF': []},
    }
    date_range = [today - timedelta(days=i) for i in range(10, -1, -1)]
    chart_dates = [d.strftime('%Y-%m-%d') for d in date_range]

    for client in clients:
        data = FpdcData.objects.filter(
            client=client,
            stored_date__range=(start_date, today)
        ).order_by('stored_date')
        data_map = {d.stored_date: d for d in data}
        prev_NOPO = prev_NPF = None
        for d in date_range:
            entry = data_map.get(d)
            if entry:
                Net_Call_INDEX = entry.Opt_IndeX_CallLong - entry.Opt_Index_CallShort
                Net_Put_INDEX = entry.Opt_Index_PutLong - entry.Opt_Index_PutShort
                Net_OI_positions_Options = Net_Call_INDEX - Net_Put_INDEX
                NET_Positions_Future = entry.Fut_Index_Long - entry.Fut_Index_Short
                if prev_NOPO is not None:                                   
                    change_in_NOPO = round(Net_OI_positions_Options - prev_NOPO, 1)
                    change_in_NPF = round(NET_Positions_Future - prev_NPF, 1)
                else:
                    change_in_NOPO = 0
                    change_in_NPF = 0
                prev_NOPO = Net_OI_positions_Options
                prev_NPF = NET_Positions_Future
            else:
                change_in_NOPO = 0
                change_in_NPF = 0
            chart_data[client]['NOPO'].append(change_in_NOPO)
            chart_data[client]['NPF'].append(change_in_NPF)

    return render(request, 'app/fpdcStrength_chart.html', {
        'fpdc_chart_dates': chart_dates,
        'fpdc_chart_data': chart_data,
    })

def premarket_last_7_days(request):
    # Redirect to NIFTY option chain with default expiry date
    today = datetime.now().date()
   
    expiry_date = today.strftime('%d-%b-%Y')
    return redirect('optionChain', symbol='NIFTY', expiry_date=expiry_date)

def PreDatacsv(request):
    path = r"C:\Users\HAI\OneDrive\Desktop\DATAFILES"
    files = os.listdir(path)
    for file in files:
        print(f"Processing file: {file}")
        PreTable(path, file)  # Pass both path and file to PreTable
        os.remove(path + "\\" + file)
    return redirect('index')

def PreTable(path, file):
    csv_path = os.path.join(path, file)
    
    # Read entire CSV first to detect the correct column name
    df = pd.read_csv(csv_path, header=0)
    
    # Normalize column names by stripping whitespace and converting to lowercase
    df.columns = df.columns.str.strip().str.lower()
    
    # Debug: Print the column names
    # print(f"Columns in CSV file: {list(df.columns)}")
    
    # Check for the column names
    if 'preOpen_NIFTY 50' in df.columns:
        pre_open_col = 'pre open nifty 50'
    elif 'preopen_nifty 50' in df.columns:
        pre_open_col = 'preopen_nifty 50'
    else:
        raise ValueError(f"CSV file must contain either 'Pre Open NIFTY 50' or 'preOpen_NIFTY 50' column. Found columns: {list(df.columns)}")
    
    # Convert DateTime column to datetime
    df["datetime"] = pd.to_datetime(df["datetime"])
    
    # Get date from first row of DateTime column
    storedDate = df["datetime"].iloc[0].date()
    
    # Extract NIFTY values using the detected column name and store only the integer part
    N_Open = int(float(df.iloc[0][pre_open_col]))
    N_High = int(float(df[pre_open_col].max()))
    N_Low = int(float(df[pre_open_col].min()))
    N_Close = int(float(df.iloc[-1][pre_open_col]))
    
    # Create and save PreMarketData object
    dataInsert = PreMarketData(
        store_date=storedDate,
        N_Open=N_Open,
        N_High=N_High,
        N_Low=N_Low,
        N_Close=N_Close
    )
    dataInsert.save()
    
def pre_market_data_view(request):
     pre_market_data = PreMarketData.objects.order_by('-store_date').all()
     return render(request, 'app/pre_market_data.html', {'pre_market_data': pre_market_data})

def LiveDatacsv(request):
    path = r"C:\Users\HAI\OneDrive\Desktop\live pre"
    files = os.listdir(path)
    
    for file in files:
        try:
            # Read CSV and create DataFrame
            file_path = os.path.join(path, file)
            df = pd.read_csv(file_path)
            
            # Strip any leading/trailing spaces from column names
            df.columns = df.columns.str.strip()
            
            # Convert DateTime column to datetime
            df['DateTime'] = pd.to_datetime(df['DateTime'], format='%Y-%m-%d %H:%M:%S')
            df.dropna(thresh=1)
            
            current_date = datetime.now().date()  # Get current date
            
            # Process each row
            for val in df['NIFTY 50']:
                # Check and update Open values
                f1 = PreMarketData.objects.filter(N_Open=val)
                if f1.exists():
                    f1.update(LN_Open='Y', f_date=current_date, LN_match='Open')
                
                # Check and update High values    
                f2 = PreMarketData.objects.filter(N_High=val)
                if f2.exists():
                    f2.update(LN_High='Y', f_date=current_date, LN_match='High')
                
                # Check and update Low values
                f3 = PreMarketData.objects.filter(N_Low=val)
                if f3.exists():
                    f3.update(LN_Low='Y', f_date=current_date, LN_match='Low')
                
                # Check and update Close values
                f4 = PreMarketData.objects.filter(N_Close=val)
                if f4.exists():
                    f4.update(LN_Close='Y', f_date=current_date, LN_match='Close')
            
            print(f"Processed file: {file}")
            
        except Exception as e:
            print(f"Error processing {file}: {str(e)}")
    
    return redirect('index')


def level_analysis_view(request):
    from datetime import timedelta
    today = timezone.now().date()
    days = 30
    date_range = [today - timedelta(days=i) for i in range(days-1, -1, -1)]
    strike_prices = sorted(set(LevelAnalysisData.objects.values_list('strike_price', flat=True)))

    # Prepare data: {strike_price: {date: LevelAnalysisData instance}}
    data = {sp: {d: None for d in date_range} for sp in strike_prices}
    qs = LevelAnalysisData.objects.filter(store_date__in=date_range)
    for entry in qs:
        data[entry.strike_price][entry.store_date] = entry

    context = {
        'date_range': date_range,
        'strike_prices': strike_prices,
        'data': data,
    }
    return render(request, 'app/level_analysis.html', context)

def get_premarket_touch_count(premarket_7days, current_market_price):
    """
    Returns a tuple: (list of dicts with match info, count of touches)
    Each dict in the list has keys: 'row', 'open_match', 'high_match', 'low_match', 'close_match'
    """
    touch_count = 0
    match_info = []
    for row in premarket_7days:
        open_match = (row.N_Open == current_market_price)
        high_match = (row.N_High == current_market_price)
        low_match = (row.N_Low == current_market_price)
        close_match = (row.N_Close == current_market_price)
        if open_match or high_match or low_match or close_match:
            touch_count += 1
        match_info.append({
            'row': row,
            'open_match': open_match,
            'high_match': high_match,
            'low_match': low_match,
            'close_match': close_match,
        })
    return match_info, touch_count
