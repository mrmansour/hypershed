from scipy.spatial import distance
from collections import deque
import numpy as np
from numpy.linalg import norm
import json
#from pyemd import emd
from scipy.signal import gaussian
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.spatial.distance import pdist,squareform
import matplotlib.pyplot as plt
import networkx as nx
from sklearn.metrics import calinski_harabaz_score,silhouette_score

class HyperGraph:    
    def __init__(self,mode='number'):
        self.edge=dict()#data structures
        self.node=dict()
        self._nodesOfEdge=dict() #links
        self._edgesOfNode=dict()
        self._edgeLevel=dict() # level of edges
        self._parentEdge=dict()
        self._childrenEdges=dict()
        self._psi=dict() #edge group in the next level
        self._costMatrix=None
        self._distCache=dict() #distance cache (e1,e2)
        self._FminCache=dict() # Fminus cache (e)
        self._nId=dict() # nodes -> ids (to keep consisten across saves)
        #        self._usedDists=dict() #TODO DEBUG        
        self._mode=mode


    def _text_cosine_dist(self, fv1, fv2):
        return 1-(fv1 * fv2.T)[0,0]



    def _fg(self,t,c):
        w=gaussian(t,t/3)
        t2=np.floor(t/2)
        w=np.concatenate((w[-(t2):],w[:t-t2]))
        w=2-np.concatenate((w[-c:],w[:-c]))
        return(w)


    def _buildCostMatrix(self,n,m):
        distance_matrix=np.zeros((n,m))
        for i in range(m):
            distance_matrix[i]=self._fg(n,i)
        return(distance_matrix)


    def edgeLevel(self,e):
        if (e in self._edgeLevel):
            return(self._edgeLevel[e])
    def edges(self,level):
        return(sorted(list([x for x in self.edge.keys() if self._edgeLevel[x]==level])))
    
    def nodes(self):
        return(sorted(list(self.node.keys())))
    
    def add_node(self,n):
        if (n not in self.node):
            self.node[n]=dict()
        if (n not in self._edgesOfNode):
            self._edgesOfNode[n]=[]
            
    def add_edge(self,id,nodes,level):        
        self._edgeLevel[id]=level
        
        if id not in self.edge:
            self.edge[id]=dict()
            
        if id not in self._nodesOfEdge:
            self._nodesOfEdge[id]=nodes
        else:
            self._nodesOfEdge[id].extend(nodes)
            
        for n in nodes:
            self.add_node(n)
            self._edgesOfNode[n].append(id)

    def edgesOfNode(self,n,level=False):
        if (n in self._edgesOfNode):
            if (level==False) and (level!=0):
                return(self._edgesOfNode[n])
            else:
                return([x for x in self._edgesOfNode[n] if (self._edgeLevel[x]==level)])
        else:
            return(None)
        
    def nodesOfEdge(self,e):
        if (e in self._nodesOfEdge):
            return(self._nodesOfEdge[e])
        else:
            return(None)
        
    def neighborsEdge(self,e,level=False):
        res=[]
        for n in self.nodesOfEdge(e):
            res.extend(self.edgesOfNode(n,level))
        res=set(res)
        res.remove(e)
        if (level!=False) or (level==0):
            res=[x for x in res if self._edgeLevel[x]==level]
        return(sorted(res))
    
    def neighborsNode(self,n,level):
        res=[]
        for e in self.edgesOfNode(n,level):
            res.extend(self.nodesOfEdge(e))
        res=set(res)
        res.remove(n)
        return(res)

    def _Fminus(self,x,level):
        if (x in self._FminCache):
            return(self._FminCache[x])
        
        neigh=self.neighborsEdge(x,level)
        minval=float('inf')
        for e in neigh:
            d=self._wdist(x,e)
            minval=min((minval,d))
        self._FminCache[x]=minval
        return(minval)

    def _kernel(self,e1,e2):
        return(np.exp(-np.power(norm(self.edge[e1]['fv']-self.edge[e2]['fv']),2)/len(self.edge[e1]['fv'])))
    
    def _wdist(self,E1,E2):
        e1=min((E1,E2))
        e2=max((E1,E2))
        if (e1 in self._distCache):
            if (e2 in self._distCache[e1]):
                return(self._distCache[e1][e2])
        else:
            self._distCache[e1]=dict()
            
        #text mode
        if self._mode=='text':
            cdist=self._text_cosine_dist(self.edge[e1]['fv'],self.edge[e2]['fv'])
        else:
            v1=np.array(self.edge[e1]['fv'],dtype=float)
            s1=np.sum(v1)
            if (s1<1E-6):
                s1=1
            v2=np.array(self.edge[e2]['fv'],dtype=float)
            s2=np.sum(v2)
            if (s2<1E-6):
                s2=1
            cdist=distance.cosine(v1/s1,v2/s2)
            #cdist=distance.euclidean(v1,v2)
            
        self._distCache[e1][e2]=cdist
        return(cdist)
                
        #return(distance.euclidean(self.edge[e1]['fv'],self.edge[e2]['fv']))

        #
            
        #return()

        #kii=self._kernel(e1,e1)
        #kij=self._kernel(e1,e2)
        #kjj=self._kernel(e2,e2)
        #return(np.sqrt(kii-2*kij+kjj))
    
    def _stream(self,x,level,psi=False):
        L=[x,]
        lp=deque([x,])
        while (len(lp)>0):
            y=lp.popleft()
            breadth_first=True
#            print("\t\t WARNING - using minimum distance to merge! hg.py line 177!")
            allZ=[z for z in self.neighborsEdge(y,level) if (z not in L) and (self._wdist(y,z)==self._Fminus(y,level))]# and (self._wdist(y,z)<0.5)]
            if (not allZ):
                break
            for z in allZ:
                if (not breadth_first):
                    break
                if (psi) and (psi[z]>=0):
                    return([L,psi[z]])
                elif self._Fminus(z,level)<self._Fminus(y,level):
                    L.append(z)
                    lp.clear()
                    lp.append(z)
                    breadth_first=False
                else:
                    L.append(z)
                    lp.append(z)
        return (L,-1)

    
    def watershed(self,level):
        psi=dict()
        for e in self.edges(level):
            psi[e]=-1
        nb_labs=0
        for x in self.edges(level):
            if (psi[x]==-1):
                L,lab=self._stream(x,level,psi)
                if (lab==-1):
                    nb_labs+=1
                    for e in L:
                        psi[e]=nb_labs
                else:
                    for e in L:
                        psi[e]=lab
#                for i in range(1,len(L)):
#                    e1=min((L[i-1],L[i]))
#                    e2=max((L[i-1],L[i]))
#                    self._usedDists[(e1,e2)]=self._distCache[e1][e2]
        return(psi)

    def kmeans(self,levelin,K=8):
        allE=self.edges(levelin)
        X=np.zeros((len(allE),len(self.edge[allE[0]]['fv'])))
        for i in range(len(allE)):
            e=allE[i]
            X[i,:]=self.edge[e]['fv']

        clusters= KMeans(n_clusters=K).fit_predict(X)
        self._psi=dict()
        for i in range(len(allE)):
            self._psi[allE[i]]=int(clusters[i])


    def _nodesOfCluster(self,level):
        nodesOfCluster=dict()        
        for n in self.nodes():
            cls=set([self._psi[e] for e in self.edgesOfNode(n,level)])
            if True:#(len(cls)>1): #more than one cluster around this node
                for c in cls:
                    if (c not in nodesOfCluster):
                        nodesOfCluster[c]=[]
                    nodesOfCluster[c].append(n)
        return(nodesOfCluster)

    
                        
    def cluster(self,levelin,levelout):
        psi=self.watershed(levelin)
        #DEBUG
#        plt.figure()
#        plt.hist(list(self._usedDists.values()),10)
#        plt.savefig('hist.png')
#        plt.close()

        
        for e in psi:
            self._psi[e]=psi[e]


        nodesOfCluster=self._nodesOfCluster(levelin)


        fv=dict()
        newNames=dict()
        tooltips=dict()
        for e in self.edges(levelin):
            k=psi[e]
            if (k not in fv):
                fv[k]=[]
                newNames[k]=''
                tooltips[k]='<list>'

            fv[k].append(self.edge[e]['fv'])
            newNames[k]=newNames[k]+self.edge[e]["name"]+"; "
            if ("tooltip" in self.edge[e]):
                tooltips[k]=tooltips[k]+self.edge[e]["tooltip"].replace("<list>","").replace("</list>","")
            else:
                tooltips[k]=tooltips[k]+"<li>"+self.edge[e]["name"]+"</li>"

        for k in newNames:
            newNames[k]=newNames[k][:-2] #removing trailing ;
            tooltips[k]=tooltips[k]+"</list>"
            
            

        for e in nodesOfCluster:
            ename='{0}_{1:02d}'.format(levelout,e)
            self.add_edge(ename,nodesOfCluster[e],levelout)
            self.edge[ename]['name']=newNames[e]
            self.edge[ename]["tooltip"]=tooltips[e]
            
            if (len(fv[e])<=2):
                self.edge[ename]['fv']=fv[e][0]
            else:
                #fv corresponding to the element with smallest distance to all others
                #self.edge[ename]['fv']=fv[e][np.argmin(np.sum(distance.squareform(distance.pdist(np.array(fv[e]),'cosine')),axis=0))]
                #mean
                self.edge[ename]['fv']=np.sum(fv[e],0)
                s=np.sum(self.edge[ename]['fv'])
                if (s>1E-6):
                    self.edge[ename]['fv']=self.edge[ename]['fv']/s
        #print the centers of each cluster
        done=[]
        for e in psi:
            if (psi[e] not in done):
                done.append(psi[e])
                L=self._stream(e,levelin)[0]
                if (len(L)>1):
                    print("Center - group  {0} - {1}".format(psi[e],set(self.nodesOfEdge(L[-1])).intersection(set(self.nodesOfEdge(L[-2])))))

            
                

    def toGraph(self,layer):
        G=nx.Graph()
        allE=self.edges(layer)
        for e1 in allE:
            for e2 in allE:
                if (e1!=e2):
                    s1=set(self.nodesOfEdge(e1))
                    s2=set(self.nodesOfEdge(e2))
                    if (len(s1&s2)>0):
                        G.add_edge(e1,e2)
                        G.node[e1]['class']=self._psi[e1]
                        G.node[e2]['class']=self._psi[e2]
                        G.node[e1]['name']=self.edge[e1]['name']
                        G.node[e2]['name']=self.edge[e2]['name']
                        G.edge[e1][e2]['weight']=self._wdist(e1,e2)
                        
        return(G)
        

    def projFeatureVectors(self,fname,layer):
        allE=self.edges(layer)
        X=np.zeros((len(allE),len(self.edge[allE[0]]['fv'])))
        colors=[]
        for i in range(len(allE)):
            e=allE[i]
            X[i,:]=self.edge[e]['fv']
            colors.append(self._psi[e])
        if (len(set(colors))==17):
            cmap=np.array([[0x1F,0x77,0xB4],
                           [0xAE,0xC7,0xE8],
                           [0xFF,0x7F,0x0E],
                           [0xFF,0xBB,0x78],
                           [0x2C,0xA0,0x2C],
                           [0x98,0xDF,0x8A],
                           [0xD6,0x27,0x28],
                           [0xFF,0x98,0x86],
                           [0x94,0x67,0xBD],
                           [0xC5,0xB0,0xD5],
                           [0x8C,0x56,0x4B],
                           [0xC4,0x9C,0x94],
                           [0xE3,0x77,0xC2],
                           [0xF7,0xB6,0xD2],
                           [0x7F,0x7F,0x7F],
                           [0xC7,0xC7,0xC7],
                           [0xBC,0xBD,0x22]])/float(0xFF)
            colors=[cmap[x-1,:].tolist() for x in colors]

            
        model = TSNE(n_components=2, random_state=0, metric='cosine', perplexity=3)
        
        Y=model.fit_transform(X)
        plt.ioff()
        plt.scatter(Y[:,0],Y[:,1],s=40,c=colors)
        plt.axis('equal')
        plt.savefig(fname)
        plt.show()

        
    def computeScore(self,layer,metric='euclidean'):
        # FAIRNESS DISCLAIMER: I implemented this, but I'm not
        # inclined to include the results on the paper, not because we
        # lose in all scores, but because kmeans solves a different
        # problem (it ignores the topology), and these scores assume
        # different hypothesis (similarity intra cluster,
        # dissimilarity inter cluster - which is not entirely true in
        # our case) - How do you evaluate an image segmentation
        # without the ground truth?
        allE=self.edges(layer)
        X=np.zeros((len(allE),len(self.edge[allE[0]]['fv'])))
        for i in range(len(allE)):
            e=allE[i]
            X[i,:]=self.edge[e]['fv']
        print('silhouette_score {0}'.format(silhouette_score(X,[self._psi[e] for e in allE],metric=metric)))            
        print('calinski_harabaz_score {0}'.format(calinski_harabaz_score(X,[self._psi[e] for e in allE])))

        C=list(set(self._psi.values()))
        inds=dict()
        for c in C:
            inds[c]=[]
        for i in range(len(allE)):
            inds[self._psi[allE[i]]].append(i)

        fd=[]
        for c in C:
            cX=X[inds[c],:]
            N=cX.shape[0]
            if (N>1):
                D=squareform(pdist(cX,metric=metric))
                fd.append(np.sum(D)/(N**2-N))

#        print(fd)
        print('fd score {0}'.format(np.mean(fd)))
        
        print('\n')

    def _edgesOrder(self,level):
        if (self._psi):
            nc=self._nodesOfCluster(level)
            clOrder=sorted([k for k in nc],key=lambda x: nc[x])
            res=[]
            for c in clOrder:
                for e in self.edges(level):
                    if (self._psi[e]==c):
                        res.append(e)
        else:
            res=self.edges(level)            

        return(res)
        
    
    def saveJson(self,level,fname,onlyBorderNodes=False,allEdges=True):
        res=dict()
        res['nodes']=[]
        res['links']=[]
        nUsed=[]
        border=dict()
        i=0
        edges=self._edgesOrder(level)
        
        for e in edges:
            allE=self.nodesOfEdge(e)
            todo=[]
            if (onlyBorderNodes):
                for n in allE:
                    if (n not in border):
                        border[n]=len( set([self._psi[e] for e in self.edgesOfNode(n,level)]))>1
                    if (border[n]):
                        todo.append(n)
                allE=todo
                    
            for n in allE:
                if n not in self._nId:
                    self._nId[n]=i
                if n not in nUsed:
                    res['nodes'].append({'id':self._nId[n],"name":self.node[n]['name']})
                    i+=1
            if (e in self._psi):
                group=self._psi[e]
            else:
                group=0;

            useEdge=True
            if (not allEdges) and (onlyBorderNodes):
                if not allE:
                    useEdge=False

            
            if (useEdge):
                if ('tooltip' in self.edge[e]):
                    tooltip=self.edge[e]["tooltip"]
                else:
                    tooltip=self.edge[e]["name"]
                    
                res['links'].append({'name':self.edge[e]['name'], "tooltip": tooltip,'group':group,'children':[self._nId[allE[i]] for i in range(len(allE))]})

        print("Saved level {0} - {1} groups\n\n".format(level,group))
        with open(fname, 'w') as outfile:
            json.dump(res, outfile)
            
            






        
