"""
This Python script is provided as an educational resource to help you explore the PLAXIS Python API. Please note the following terms:
 
1. Risk and Understanding: By using this script, you acknowledge that you are responsible for understanding and managing any risks associated with its use. Bentley is not liable for any issues that may arise.
2. No Warranty: The script is provided "as-is" without any warranty, as outlined in Article 22 and 23 of the EULA for Bentley software (version 2023-10-16, https://www.bentley.com/legal/eula/).
3. License Requirement: A valid PLAXIS license is required to use this script.
4. Feedback and Intellectual Property: Any feedback or suggestions you provide regarding this script will become the exclusive property of Bentley, as outlined in Article 3 of the Bentley EULA.
5. No Support: Bentley is not obligated to provide support or maintenance for this script.
 
© 2025 Seequent, The Bentley Subsurface Company. All rights reserved.
"""
from plxscripting.easy import *
import matplotlib.pyplot as plt

# Initialize input scripting server
s_o, g_o = new_server()
#
maxLoad = 53.2
phaseLoading = g_o.Phases[-2]
phaseUnloading = g_o.Phases[-1]
nodeTop = g_o.Nodes[1]
nodeBottom = g_o.Nodes[0]
#
loadNum = [0]
upperPlateNumDisp = [0]
lowerPlateNumDisp = [0]
upperPlateExpLoad = [0, 3.27291769148986,
                     8.02177121185674, 10.7810342912454,
                     13.3481648391754, 15.9793713007188,
                     18.5463114298862, 21.3056697186562,
                     23.8727050572049, 26.5683682698868,
                     29.2638410638061, 31.8308764023548,
                     34.5905203192687, 37.2858979038067,
                     39.9174852028753, 42.5488820831812,
                     45.3086212094765, 47.811961471937,
                     50.3793776480109, 53.1399736587378,
                     42.2949586632602, 31.8989511099827,
                     21.1819927323505, 10.7859851790729,
                     0.0687411732969418]
upperPlateExpDisp = [5.93471810088956E-05, 0.000267062314540055,
                     0.000682492581602371, 0.000474777448071211,
                     0.00109792284866468, 0.001513353115727,
                     0.00172106824925815, 0.00172106824925815,
                     0.00213649851632047, 0.00317507418397625,
                     0.00379821958456972, 0.00421364985163204,
                     0.00483679525222551, 0.00525222551928783,
                     0.00649851632047477, 0.00732937685459939,
                     0.00816023738872403, 0.00961424332344213,
                     0.010860534124629, 0.0135608308605341,
                     0.0133531157270029, 0.0127299703264094,
                     0.0118991097922848, 0.0112759643916913,
                     0.00982195845697328]
lowerPlateExpLoad = [0, 3.27253685396467,
                     8.08508545041971, 10.7156254462939,
                     13.3460702327869, 15.9765150192799,
                     18.5425030546343, 21.3007188308288,
                     23.9944778558847, 26.6234945016582,
                     29.2520351005252, 31.8804804900109,
                     34.5723353274409, 37.3280756597216,
                     40.0195496596264, 42.5187959186911,
                     45.2102699185959, 47.8379536330313,
                     50.3374855202399, 53.0900839429378,
                     42.3090496516923, 31.8494422317079,
                     21.1977974896459, 10.8030276583252,
                     0]
lowerPlateExpDisp = [0, -0.000563798219584573,
                     -0.00118694362017804, -0.00222551928783383,
                     -0.00347181008902077, -0.00471810089020771,
                     -0.00658753709198813, -0.00908011869436202,
                     -0.0121958456973293, -0.0165578635014836,
                     -0.0219584569732937, -0.027566765578635,
                     -0.0348367952522255, -0.0427299703264095,
                     -0.0508308605341246, -0.0583086053412462,
                     -0.0664094955489614, -0.0736795252225519,
                     -0.0805341246290801, -0.0952818991097922,
                     -0.0959050445103857, -0.0952818991097922,
                     -0.093620178041543, -0.0915430267062314,
                     -0.0875964391691394]

# Fetch results

unitLength = g_o.GeneralInfo.UnitLength.value
unitForce = g_o.GeneralInfo.UnitForce.value
loadNum = (loadNum +
           [step.Reached.SumMstage.value * maxLoad for step in phaseLoading.Steps.value] +
           [(1 - step.Reached.SumMstage.value) * maxLoad for step in phaseUnloading.Steps.value])
result = g_o.ResultTypes.Soil.Uz
upperPlateNumDisp = (upperPlateNumDisp +
                     [g_o.getcurveresults(nodeTop, step, result) for step in phaseLoading.Steps.value] +
                     [g_o.getcurveresults(nodeTop, step, result) for step in phaseUnloading.Steps.value])
lowerPlateNumDisp = (lowerPlateNumDisp +
                     [g_o.getcurveresults(nodeBottom, step, result) for step in phaseLoading.Steps.value] +
                     [g_o.getcurveresults(nodeBottom, step, result) for step in phaseUnloading.Steps.value])

# Plot results
fig, ax = plt.subplots()
ax.set_title('Displacement versus load')
ax.set_xlabel("Load ("+unitForce+"/"+unitLength+"$^2$)")
ax.set_ylabel("Uz ("+unitLength+")")
ax.scatter(upperPlateExpLoad, upperPlateExpDisp)
ax.scatter(lowerPlateExpLoad, lowerPlateExpDisp)
ax.plot(loadNum, upperPlateNumDisp, label="Upper plate")
ax.plot(loadNum, lowerPlateNumDisp, label="Lower plate")
ax.legend()
plt.xlim(left=0)
plt.grid(True, ls='--')
plt.show()

