// Minimal AKS cluster for Demo 7. Provision separately:
//   az deployment group create -g <rg> -f aks/cluster.bicep -p clusterName=<name>
//
// Wires up workload identity + OIDC issuer so the Helm chart's
// ServiceAccount can federate to the same MI used by the Container Apps
// deployment, reusing all Foundry RBAC.

param clusterName string
param location string = resourceGroup().location
@description('Object id of the user-assigned MI created by the main Bicep deployment.')
param workloadIdentityResourceId string

resource aks 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: clusterName
  location: location
  identity: { type: 'SystemAssigned' }
  sku: {
    name: 'Base'
    tier: 'Free'
  }
  properties: {
    dnsPrefix: clusterName
    enableRBAC: true
    oidcIssuerProfile: { enabled: true }
    securityProfile: {
      workloadIdentity: { enabled: true }
    }
    agentPoolProfiles: [
      {
        name: 'sys'
        mode: 'System'
        count: 2
        vmSize: 'Standard_D4s_v5'
        osType: 'Linux'
        type: 'VirtualMachineScaleSets'
        nodeLabels: {
          apps: 'llama-3-3b'
        }
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPolicy: 'cilium'
      networkDataplane: 'cilium'
    }
  }
}

// Federate the user-assigned MI to the SA used by Helm (kubernetes-namespace = trial-matcher).
resource fed 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  name: '${last(split(workloadIdentityResourceId, '/'))}/aks-trial-matcher'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:trial-matcher:trial-matcher'
    audiences: ['api://AzureADTokenExchange']
  }
}

output aksClusterName string = aks.name
output oidcIssuerUrl string = aks.properties.oidcIssuerProfile.issuerURL
