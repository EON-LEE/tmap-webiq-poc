// One TMAP WebIQ POC environment in one resource group. Deployed by scripts/provision.py:
// first with deployApp=false (shared resources), then with deployApp=true once the image,
// agents and sign-in app exist. Secrets are never outputs.

targetScope = 'resourceGroup'

type resourceNames = {
  app: string
  environment: string
  identity: string
  workspace: string
  account: string
  project: string
  registry: string
  bing: string
  bingConnection: string
}

type modelDeployment = {
  name: string
  version: string
  sku: string
  capacity: int
}

type agentReference = {
  name: string
  version: string
}

param location string = resourceGroup().location
param names resourceNames
param model modelDeployment

@description('Object ID of the identity running the deployment. It gets Foundry User on the project to register agents.')
param deployerPrincipalId string

@allowed(['User', 'ServicePrincipal'])
param deployerPrincipalType string = 'User'

param deployApp bool = false
param image string = ''
param bingAgent agentReference = { name: '', version: '' }
param webiqAgent agentReference = { name: '', version: '' }
param webSearchToolbox string = ''
param voiceName string = 'ko-KR-SunHiNeural'
param signInClientId string = ''

@secure()
param signInClientSecret string = ''

param tags object = {
  workload: 'tmap-webiq-poc'
  environment: 'poc'
}

var roleIds = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}
var azureCliAppId = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
var webiqConnectionName = 'webiq-mcp'
var signInSecretName = 'aad-client-secret'
var projectEndpoint = 'https://${names.account}.services.ai.azure.com/api/projects/${names.project}'

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.workspace
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.identity
  location: location
  tags: tags
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: names.registry
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: names.account
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: names.account
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: names.project
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'TMAP WebIQ POC'
    description: 'WebIQ versus Grounding with Bing voice comparison'
  }
}

// Writes to one Foundry account are serialized; parallel writes fail with a conflict.
resource modelDeploymentResource 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: model.name
  sku: {
    name: model.sku
    capacity: model.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: model.name
      version: model.version
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [project]
}

#disable-next-line BCP081
resource bing 'Microsoft.Bing/accounts@2020-06-10' = {
  name: names.bing
  location: 'global'
  tags: tags
  kind: 'Bing.Grounding'
  sku: { name: 'G1' }
}

resource bingConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: names.bingConnection
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: bing.listKeys().key1
    }
    metadata: {
      ApiType: 'Azure'
      Location: 'global'
      ResourceId: bing.id
    }
  }
  dependsOn: [modelDeploymentResource]
}

resource appEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.environment
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource runtimeAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, identity.id, roleIds.acrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.acrPull)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource runtimeVoice 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, identity.id, roleIds.cognitiveServicesUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource runtimeFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, identity.id, roleIds.foundryUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.foundryUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deployerFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, deployerPrincipalId, roleIds.foundryUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.foundryUser)
    principalId: deployerPrincipalId
    principalType: deployerPrincipalType
  }
}

var appUrl = 'https://${names.app}.${appEnvironment.properties.defaultDomain}'

resource app 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: names.app
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    environmentId: appEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: signInSecretName
          value: signInClientSecret
        }
      ]
    }
    template: {
      containers: [
        {
          name: names.app
          image: image
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'TMAP_AUTH_MODE', value: 'managed_identity' }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'GWB_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'TMAP_POC_MODEL_DEPLOYMENT', value: model.name }
            { name: 'TMAP_VOICE_ENDPOINT', value: 'https://${names.account}.cognitiveservices.azure.com' }
            { name: 'TMAP_VOICE_NAME', value: voiceName }
            { name: 'TMAP_BING_AGENT_NAME', value: bingAgent.name }
            { name: 'TMAP_BING_AGENT_VERSION', value: bingAgent.version }
            { name: 'TMAP_WEBIQ_AGENT_NAME', value: webiqAgent.name }
            { name: 'TMAP_WEBIQ_AGENT_VERSION', value: webiqAgent.version }
            { name: 'TMAP_WEB_SEARCH_TOOLBOX', value: webSearchToolbox }
            { name: 'TMAP_ALLOWED_ORIGINS', value: appUrl }
            { name: 'TMAP_TRACE_EXPORTER', value: 'none' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [runtimeAcrPull, runtimeVoice, runtimeFoundry]
}

resource signIn 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployApp) {
  parent: app
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'AzureActiveDirectory'
      excludedPaths: ['/healthz']
    }
    identityProviders: {
      azureActiveDirectory: {
        registration: {
          openIdIssuer: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
          clientId: signInClientId
          clientSecretSettingName: signInSecretName
        }
        validation: {
          allowedAudiences: ['api://${signInClientId}']
          defaultAuthorizationPolicy: {
            allowedApplications: [signInClientId, azureCliAppId]
          }
        }
      }
    }
    login: { preserveUrlFragmentsForLogins: false }
  }
}

output projectEndpoint string = projectEndpoint
output projectId string = project.id
output bingConnectionId string = bingConnection.id
output webiqConnectionId string = '${project.id}/connections/${webiqConnectionName}'
output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output appUrl string = appUrl
