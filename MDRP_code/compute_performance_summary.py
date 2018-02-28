from __future__ import print_function
import pandas as pd
pd.set_option('display.expand_frame_repr', False)
import os
import numpy as np
import bisect
import sys
'''
This script takes as input (at most) three directories, in the following order:
    1. instance directory: it is expected to contain files orders.txt, couriers.txt, restaurants.txt, and instance_parameters.txt
    2. input (solution) directory: it is expected to contain files assignment_solution_info.txt, orders_solution_info.txt, couriers_solution_info.txt
    3. output (summary) directory: the place where the output files will be stored
The script produces two files, named 'feasibility_check.txt' and 'solution_performance.txt'.
Example call:
    python compute_performance_summary.py instance_dir=instances/an_instance input_dir=solutions/my_instance/my_algorithm output_dir=performance_summaries/an_instance/my_algorithm
'''

# default directory
folder_default=os.path.join(os.path.curdir,'test_sampling_orders')

# some methods defined on their own for clarity
def traveltime(origin_id,destination_id,meters_per_minute,locations):
    dist=np.sqrt((locations.at[destination_id,'x']-locations.at[origin_id,'x'])**2\
                +(locations.at[destination_id,'y']-locations.at[origin_id,'y'])**2)
    tt=np.ceil(dist/meters_per_minute)
    return tt

def parse_console_input_and_define_parameter_values(console_input):
    instance_dir=next((p for p in console_input if 'instance_dir=' in p),None)
    if instance_dir:
        # (containing orders.txt, couriers.txt, restaurants.txt and instance_parameters.txt)
        _,instance_dir=instance_dir.split('=')
        if instance_dir.startswith('"') and instance_dir.endswith('"'):
            instance_dir = instance_dir[1:-1]
        elif instance_dir.startswith("'") and instance_dir.endswith("'"):
            instance_dir = instance_dir[1:-1]
    else:
        # if not provided, try the default instance directory
        instance_dir=folder_default 

    input_dir=next((p for p in console_input if 'input_dir=' in p),None)
    if input_dir:
        _,input_dir=input_dir.split('=')
        if input_dir.startswith('"') and input_dir.endswith('"'):
            input_dir = input_dir[1:-1]
        elif input_dir.startswith("'") and input_dir.endswith("'"):
            input_dir = input_dir[1:-1]
    else:
        input_dir=instance_dir

    output_dir=next((p for p in console_input if 'output_dir=' in p),None)
    if output_dir:
        _,output_dir=output_dir.split('=')
        if output_dir.startswith('"') and output_dir.endswith('"'):
            output_dir = output_dir[1:-1]
        elif output_dir.startswith("'") and output_dir.endswith("'"):
            output_dir = output_dir[1:-1]
    else:
        output_dir=instance_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return instance_dir,input_dir,output_dir

def read_instance_information(instance_dir):
    orders=pd.read_table(os.path.join(instance_dir,'orders.txt'))
    restaurants=pd.read_table(os.path.join(instance_dir,'restaurants.txt'))
    couriers=pd.read_table(os.path.join(instance_dir,'couriers.txt'))
    instanceparams=pd.read_table(os.path.join(instance_dir,'instance_parameters.txt'))

    order_locations=pd.DataFrame(data=[orders.order,orders.x,orders.y]).transpose()
    order_locations.columns=['id','x','y']
    restaurant_locations=pd.DataFrame(data=[restaurants.restaurant,restaurants.x,restaurants.y]).transpose()
    restaurant_locations.columns=['id','x','y']
    courier_locations=pd.DataFrame(data=[couriers.courier,couriers.x,couriers.y]).transpose()
    courier_locations.columns=['id','x','y']
    locations=pd.concat([order_locations,restaurant_locations,courier_locations])
    locations.set_index('id',inplace=True)

    orders.set_index('order',inplace=True)
    couriers.set_index('courier',inplace=True)
    restaurants.set_index('restaurant',inplace=True)

    meters_per_minute=instanceparams.at[0,'meters_per_minute']
    pickup_service_minutes=instanceparams.at[0,'pickup service minutes']
    dropoff_service_minutes=instanceparams.at[0,'dropoff service minutes']
    target_click_to_door=instanceparams.at[0,'target click-to-door']
    pay_per_order=instanceparams.at[0,'pay per order']
    guaranteed_pay_per_hour=instanceparams.at[0,'guaranteed pay per hour']
    return orders,restaurants,couriers,instanceparams,locations,meters_per_minute,\
           pickup_service_minutes,dropoff_service_minutes,target_click_to_door,\
           pay_per_order,guaranteed_pay_per_hour

def read_solution_information(input_dir):
    # read assignment solution file
    with open(os.path.join(input_dir,'solution_info_assignments.txt'),'r') as f:
        #raw_assignments=[a.replace(' ','\t').replace('\n','').split('\t') for a in f.readlines()]
        raw_assignments=[a.split() for a in f.readlines()]
        assignments=[[int(float(a[0])),int(float(a[1])),a[2],a[3:]] for a in raw_assignments[1:]]
        order_pickup_times=pd.Series(*zip(*[(int(float(a[1])),o) for a in raw_assignments[1:] for o in a[3:]]))
    assignment_sol=pd.DataFrame(data=assignments,columns=['assignment_time','pickup_time','courier','bundle'])

    # read order solution file
    order_sol=pd.read_table(os.path.join(input_dir,'solution_info_orders.txt'),\
                             #names=['order','placement_time','restaurant','latitude','longitude',\
                             #'ready_time','pickup_time','dropoff_time','courier'],\
                             sep=' ')
    order_sol.placement_time=pd.to_numeric(order_sol.placement_time,errors='coerce')
    order_sol.ready_time=pd.to_numeric(order_sol.ready_time,errors='coerce')
    order_sol.pickup_time=pd.to_numeric(order_sol.pickup_time,errors='coerce')
    order_sol.dropoff_time=pd.to_numeric(order_sol.dropoff_time,errors='coerce')
    order_sol.set_index('order',inplace=True)

    # read courier solution file
    with open(os.path.join(input_dir,'solution_info_couriers.txt'),'r') as f:
        courier_sol={}
        courier_id=None
        courier_moves=[]
        header=next(f)
        #print(repr(header))
        line=header.split()
        try:
            departure_time=int(float(line[1]))
        except:
            print('detected header line:',header)
            pass
        else: # if the line is not a header
            courier_id=line[0]
            origin_id= line[2] if line[2]!='0' else courier_id
            destination_id=line[3].strip()
            courier_moves.append([departure_time,origin_id,destination_id])        
        for line in f:
            #print(repr(line))
            if line.isspace():
                continue
            else:
                line=line.split()
                if courier_id!=line[0]:
                    courier_sol[courier_id]=courier_moves
                    courier_moves=[]
                    courier_id=line[0]
                departure_time=int(float(line[1]))
                origin_id= line[2] if line[2]!='0' else courier_id
                destination_id=line[3].strip()
                courier_moves.append([departure_time,origin_id,destination_id])
        if courier_id not in courier_sol:
            courier_sol[courier_id]=courier_moves
        courier_sol.pop(None, None)
    return assignment_sol,order_sol,courier_sol,order_pickup_times

# Script
def compute_performance_summary(instance_dir,input_dir,output_dir):
    print('reading instance information')   
    orders,restaurants,couriers,instanceparams,locations,meters_per_minute,\
    pickup_service_minutes,dropoff_service_minutes,target_click_to_door,\
    pay_per_order,guaranteed_pay_per_hour = read_instance_information(instance_dir)
    print('reading solution information')
    assignment_sol,order_sol,courier_sol,order_pickup_times = read_solution_information(input_dir)
    
    ### Check feasibility of solution
    print('checking feasibility of the solution')
    feasibility_file=os.path.join(output_dir,'feasibility_check.txt')
    f= open(feasibility_file, "w")
    feasible=True

    # verify that each order is in at most one assignment
    bundles_per_order={}
    for o in order_sol.index:
        for b in assignment_sol.bundle:
            if o in b:
                if o in bundles_per_order:
                    bundles_per_order[o].append(b)
                else:
                    bundles_per_order[o]=[b]
    violations={o:l for o,l in bundles_per_order.items() if len(l)>1}
    if violations: 
        print('orders in more than one assignment:',file=f)
        print(*violations.keys(),sep='\n',file=f)    
        feasible=False
    else:
        print('every order is in at most one assignment: OK',file=f)

    # verify that assignments are not made before information is revealed
    violations=[]
    orders_per_bundle=[] # leverage loop to record the size of bundles
    for i,a in assignment_sol.iterrows():
        order_seq=a.bundle
        assignment_time=a.assignment_time
        #print('\n'+str(pickup)+' '+str(order_seq),end='\t')
        for o in order_seq:
            placement=orders.at[o,'placement_time']
            #print(ready,end=' ')
            if assignment_time<placement:
                violations.append((assignment_time,placement,o,a))
        orders_per_bundle.append(len(order_seq))
    if violations:
        print('\nassignments made before orders are placed:',file=f)
        print(*violations,sep='\n',file=f)
        feasible=False
    else:
        print('\nassignments are never made before information is revealed: OK',file=f)

    # verify that each assignment is picked up before the off-time of the courier
    violations=[]
    bundles_per_courier={d:0 for d in couriers.index}#leverage loop: couriers' total bundles served
    for i,a in assignment_sol.iterrows():
        offtime=couriers.at[a.courier,'off_time']
        if offtime<a.pickup_time:
            violations.append((offtime,a.pickup_time,a))
        bundles_per_courier[a.courier]+=1
    if violations:
        print('\nbundle picked up after off-time of courier:',file=f)
        print(*violations,sep='\n',file=f)
        feasible=False
    else:
        print('\nbundle picked up before off-time of courier: OK',file=f)

    # verify that, for each assignment, the pickup time is not erlier than the ready time of any order in the bundle
    violations=[]
    for i,a in assignment_sol.iterrows():
        order_seq=a.bundle
        pickup=a.pickup_time
        #print('\n'+str(pickup)+' '+str(order_seq),end='\t')
        for o in order_seq:
            ready=orders.at[o,'ready_time']
            #print(ready,end=' ')
            if ready>pickup:
                violations.append((pickup,ready,a))
    if violations:
        print('\nbundle pickup times do not respect individual ready times:',file=f)
        print(*violations,sep='\n',file=f)
        feasible=False    
    else:
        print('\nbundle pickup times respect ready times: OK',file=f)

    # verify that dropoffs occur in the right order (one assignment after another one, 
    # respecting the delivery sequence in each assigned bundle) and that and delivery 
    # service time is enforced 
    violations=[]
    for i,a in assignment_sol.iterrows():
        order_seq=a.bundle
        dropoffs=[]
        #print('\n',order_seq,end='\t')
        for o in order_seq:
            drop=order_sol.at[o,'dropoff_time']
            #print(drop,end=' ')
            if dropoffs:
                if drop<dropoffs[-1]+dropoff_service_minutes:
                    violations.append((dropoffs,drop,order_seq))
            dropoffs.append(drop)
    if violations:
        print('\ndropoffs do not follow the prescribed sequence:',file=f)
        print(*violations,sep='\n',file=f)
        feasible=False
    else:
        print('\ndropoffs follow the prescribed sequence:OK',file=f)

    # Prepare timeline for each courier: when are they in transit? when and where are
    # they not moving? While we're at it, verify that couriers do not tele-transport 
    # (arrival location is next departure location; arrival happens before departure)
    courier_timeline={}
    violations1=[]
    violations2=[]
    time_driving={}
    for d,s in courier_sol.items():
        courier_timeline[d]=lambda:None
        courier_timeline[d].times=[couriers.loc[d].on_time]
        courier_timeline[d].places=[d]
        time_driving[d]=0
        for a in s:
            if a[1]!=courier_timeline[d].places[-1]:#'current origin should be previous destination'
                violations1.append((d,a[1],courier_timeline[d].places[-1]))
            courier_timeline[d].times.append(a[0])
            courier_timeline[d].places.append('')
            tt=traveltime(a[1],a[2],meters_per_minute,locations)
            courier_timeline[d].times.append(a[0]+tt)
            courier_timeline[d].places.append(a[2])
            time_driving[d]+=tt
        if sorted(courier_timeline[d].times) != courier_timeline[d].times:#'if departures happen after arrivals, times are ordered'
            violations2.append(courier_timeline[d].times)
    if violations1:
        print('\ndiscontinuities in sequence of origin-destination pairs:',file=f)
        print(*violations1,sep='\n',file=f)
        feasible=False
    else:
        print('\ncontinuity in sequence of origin-destination pairs: OK',file=f)
    if violations2:
        print('\ndepartures sometimes happen before arrivals:',file=f)
        print(*violations2,sep='\n',file=f)
        feasible=False
    else:
        print('\ndepartures and arrival time are consistent in time: OK',file=f)

    # Verify that for each dropoff, the courier is located at the right place at the right time
    time_dropping={d:0 for d in couriers.index} #leverage loop: couriers' total dropoff service time
    orders_served={d:0 for d in couriers.index}#leverage loop: couriers' total orders served
    violations=[]
    #print(order_sol.head())
    for o_id, o_info in order_sol.iterrows():
        if o_info.courier=='courier':
            continue
        d=o_info['courier']
        if d not in orders_served:
            continue
        drop=o_info.dropoff_time
        i=bisect.bisect_left(courier_timeline[d].times,drop)-1
        loc_id=courier_timeline[d].places[i]
        if loc_id!=o_id:
            violations.append((o_id,drop,loc_id))
        time_dropping[d]+=dropoff_service_minutes
        orders_served[d]+=1
    if violations:
        print('\ninconsistency in dropoff times and locations',file=f)
        print(*violations,file=f)
        feasible=False
    else:
        print('\ndropoff times and locations are consistent:OK',file=f)

    # Verify that, for each pickup, the courier is located at the right place at the right time
    time_picking={d:0 for d in couriers.index} #leverage loop: couriers' total pickup service time (lower bound)
    violations=[]
    for a_id, a_info in assignment_sol.iterrows():
        d=a_info.courier
        o=a_info.bundle[0]
        r=orders.loc[o].restaurant
        pickup=a_info.pickup_time
        i=bisect.bisect_left(courier_timeline[d].times,pickup)-1
        loc_id=courier_timeline[d].places[i]
        if loc_id!=r:
            violations.append((o_id,r,pickup,loc_id))
        time_picking[d]+=pickup_service_minutes
    if violations:
        print('\ninconsistency in pickup times and locations',file=f)
        print(*violations,file=f)
        feasible=False
    else:
        print('\npickup times and locations are consistent:OK',file=f)

    # Verdict
    if feasible:
        print('FEASIBLE',file=f)
        print('Solution is feasible.')
    else:
        print('INFEASIBLE',file=f)
        print('Solution is not feasible. Check',feasibility_file, 'for more information')
    f.close()
    
    ### Compute performance measures of solution
    print('computing solution performance metrics')
    try:
        #print(order_sol.tail())
        #print(order_sol.dropna().tail())
        #print(len(order_sol))
        #print(len(order_sol.dropna()))
        total_delivered=len(order_sol.dropna())
    except:
        total_delivered=None
    try:
        order_performance=pd.merge(orders.drop(['x','y','restaurant'],axis=1),\
                                   order_sol.drop(['placement_time','ready_time'],axis=1),\
                                   left_index=True,right_index=True)
        #order_performance['pickup_time']=order_pickup_times
        order_performance['click-to-door']=order_performance['dropoff_time']-order_performance['placement_time']
        order_performance['ready-to-door']=order_performance['dropoff_time']-order_performance['ready_time']
        order_performance['ready-to-pickup']=order_performance['pickup_time']-order_performance['ready_time']
        order_performance['click-to-door overage']=order_performance.apply(\
                                                   lambda row:max(0,row['click-to-door']-target_click_to_door) ,axis=1)     
    except:
        order_performance=None
    try:
        courier_performance=couriers.drop(['x','y'],axis=1)
        courier_performance['shift_duration']=courier_performance['off_time']-courier_performance['on_time']
        courier_performance['guaranteed_earnings']=courier_performance['shift_duration']*guaranteed_pay_per_hour/60.0
        courier_performance['orders_delivered']=pd.Series(orders_served)
        courier_performance['bundles_delivered']=pd.Series(bundles_per_courier)
        courier_performance['orders_per_hour']=60*courier_performance['orders_delivered']/courier_performance['shift_duration']
        courier_performance['bundles_per_hour']=60*courier_performance['bundles_delivered']/courier_performance['shift_duration']
        courier_performance['order_earnings']=courier_performance['orders_delivered']*pay_per_order
        courier_performance['payment']=courier_performance.apply(lambda row: max(row['order_earnings'],row['guaranteed_earnings']),axis=1)
        courier_performance['time_driving']=pd.Series(*zip(*[(v,k) for k,v in time_driving.items()]))
        courier_performance['time_dropping']=pd.Series(*zip(*[(v,k) for k,v in time_dropping.items()]))
        courier_performance['time_picking']=pd.Series(*zip(*[(v,k) for k,v in time_picking.items()]))
        courier_performance['utilization']=(courier_performance['time_driving']+courier_performance['time_dropping']+\
                                                 courier_performance['time_picking'])/courier_performance['shift_duration']
        courier_performance.fillna({'utilization':0},inplace=True)
        total_cost=courier_performance['payment'].sum()
        proportion_trueup=len(courier_performance.loc[courier_performance['order_earnings']<courier_performance['guaranteed_earnings']])/(1.0*len(couriers))
    except:
        courier_performance=None
        total_cost=None
        proportion_trueup=None
    try:
        bundle_size=pd.DataFrame(orders_per_bundle,columns=['orders_per_bundle'])
    except:
        bundle_size=None
    if feasible:
        # write performance summary
        performance_file=os.path.join(output_dir,'solution_performance.txt')        
        with open(performance_file,'w') as f:
            print('number of orders delivered:',total_delivered,'out of',len(orders),file=f)
            print('total payment:','{0:.2f}'.format(total_cost),file=f)
            print('proportion of couriers receiving minimum guaranteed compensation:',\
                   '{0:.2f}'.format(proportion_trueup),file=f)
            print('\n',file=f)
            print(order_performance[['click-to-door','ready-to-door',\
                            'ready-to-pickup','click-to-door overage']]\
                            .describe(percentiles=[0.1,0.9])\
                            .to_string(float_format=lambda x:'{0:.2f}'.format(x)),file=f)
            print('\n',file=f)
            print(courier_performance[['orders_per_hour','bundles_per_hour','utilization',\
                                       'guaranteed_earnings','order_earnings','payment']]\
                                       .describe(percentiles=[0.1,0.9])\
                                       .to_string(float_format=lambda x:'{0:.2f}'.format(x)),file=f)
            print('\n',file=f)
            print(bundle_size.describe(percentiles=[0.1,0.9])\
                                       .to_string(float_format=lambda x:'{0:.2f}'.format(x)),file=f)
        print('Performance measures were written to file:',performance_file)
    else:
        pass    
    return feasible,total_delivered,total_cost,proportion_trueup,order_performance,courier_performance

if __name__=='__main__':
    console_input=sys.argv
    #console_input=['instance_dir=8o100t75s2p125',r'input_dir=8o100t75s2p125\results\p_31','output_dir=.']
    #console_input=['instance_dir=3o50t75s1p125']
    print(console_input)
    print(pd.__version__)
    instance_dir,input_dir,output_dir = parse_console_input_and_define_parameter_values(console_input)
    print(instance_dir,input_dir,output_dir)
    feasible,total_delivered,total_cost,proportion_trueup,order_performance,courier_performance=compute_performance_summary(instance_dir,input_dir,output_dir)